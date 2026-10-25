"""Deliberate data-quality problems plus a ground-truth register.

Every injected defect and every designed edge case is written to
EXCEPTIONS_REGISTER.csv with the check that is expected to catch it, so the QA
suites in each project can be graded against known answers.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from . import config as C
from .util import office_time, stream, to_utc, week_start

CUTOFF = datetime.combine(C.AS_OF, time(23, 59, 59))
PROGRAM_THERAPIES = {t for spec in C.PROGRAMS.values() for t in spec["therapies"]}
RECENT = week_start(C.AS_OF) - timedelta(weeks=24)


class Register:
    def __init__(self):
        self.rows = []

    def add(self, origin, defect_type, table, record_key, related_key, description, expected_check, projects):
        self.rows.append(dict(exception_id=f"EX{len(self.rows) + 1:04d}", origin=origin, defect_type=defect_type,
                              table_name=table, record_key=record_key, related_key=related_key,
                              description=description, expected_check=expected_check, projects=projects))


def _next_key(rows, field, prefix, width):
    n = max(int(r[field][len(prefix):]) for r in rows) + 1
    while True:
        yield f"{prefix}{n:0{width}d}"
        n += 1


def inject_core(t, reg, plan_umbrella, unmapped_plans):
    rng = stream("defects")
    appts = {a["appt_key"]: a for a in t["appointments"]}
    orders = {o["order_key"]: o for o in t["orders"]}
    admins_by_appt = defaultdict(list)
    for ad in t["administrations"]:
        admins_by_appt[ad["appt_key"]].append(ad)
    treated_orders = defaultdict(list)          # order -> administered appointment starts
    for a in t["appointments"]:
        if a["status"] == "Complete" and a["meds_administered"] == 1:
            treated_orders[a["order_key"]].append(a["start_local"])

    # --- designed edge cases that arise naturally (register before mutating) ---
    for a in t["appointments"]:
        if a["start_local"] <= CUTOFF and a["status"] in ("Scheduled", "Confirmed"):
            reg.add("designed_edge_case", "LATE_UPDATE_PENDING", "appointments", a["appt_key"], a["patient_key"],
                    "Visit date has passed but the completion/cancellation update had not arrived by the snapshot.",
                    "past-dated appointments still Scheduled/Confirmed", "A,19")
    by_patient = defaultdict(list)
    for a in t["appointments"]:
        by_patient[a["patient_key"]].append(a)
    for pk, rows in by_patient.items():
        flagged = [a for a in rows if a["first_patient_appt_flag"] == 1]
        treated = [a for a in rows if a["status"] == "Complete" and a["meds_administered"] == 1]
        if flagged and treated and not (flagged[0]["status"] == "Complete" and flagged[0]["meds_administered"] == 1):
            reg.add("designed_edge_case", "STALE_FIRST_FLAG", "appointments", flagged[0]["appt_key"], pk,
                    "First-appointment flag sits on a visit that was not a treated visit; the patient's real first "
                    "treatment is a later appointment.", "flag-based vs derived first-treatment comparison", "A,17")
    for ps in t["provider_specialties"]:
        if ps["is_primary"] == 0:
            reg.add("designed_edge_case", "MULTI_SPECIALTY_PROVIDER", "provider_specialties", ps["provider_key"],
                    ps["specialty_code"], "Provider carries a second specialty; joins on specialty can double-count.",
                    "distinct provider count before/after specialty join", "A,09,18")
    reg.add("designed_edge_case", "SPLIT_ZIP", "postal_county_crosswalk", "00150", "CTY04|CTY05",
            "ZIP straddles two counties; use the primary-county row to avoid duplicating providers.",
            "zip5 rows with more than one county", "A,09,18")

    # --- administrations --------------------------------------------------------
    ad_key = _next_key(t["administrations"], "admin_key", "AD", 6)
    recent_prog = [ad for ad in t["administrations"] if ad["administered_flag"] == 1
                   and ad["therapy_key"] in PROGRAM_THERAPIES and appts[ad["appt_key"]]["start_local"].date() >= RECENT]
    others = [ad for ad in t["administrations"] if ad["administered_flag"] == 1 and ad["therapy_key"] not in PROGRAM_THERAPIES]
    for src in rng.sample(recent_prog, 6) + rng.sample(others, 4):
        dup = dict(src, admin_key=next(ad_key))
        t["administrations"].append(dup)
        reg.add("injected_defect", "DUP_ADMIN_LINE", "administrations", dup["admin_key"], src["admin_key"],
                "Exact duplicate administration line (same appointment, therapy, lot, vials, time).",
                "duplicate administration content", "A,03,05,06,16")
    cancelled = [a for a in t["appointments"] if a["status"] == "Cancelled" and a["start_local"] <= CUTOFF]
    for a in rng.sample(cancelled, 3):
        row = dict(admin_key=next(ad_key), appt_key=a["appt_key"], therapy_key=a["therapy_key"], administered_flag=1,
                   vials=1, lot_code=f"LOT-X{rng.randrange(100000, 999999)}", line_number=1,
                   administered_at=a["start_local"] + timedelta(minutes=45))
        t["administrations"].append(row)
        reg.add("injected_defect", "ADMIN_ON_CANCELLED_APPT", "administrations", row["admin_key"], a["appt_key"],
                "Administration charted against an appointment whose status is Cancelled.",
                "administrations joined to non-Complete appointments", "A,03,16")

    # --- appointments -----------------------------------------------------------
    multi = sorted([pk for pk, rows in by_patient.items() if len(rows) >= 3])
    for pk in rng.sample(multi, 5):
        second = sorted(by_patient[pk], key=lambda a: a["start_local"])[1]
        second["first_patient_appt_flag"] = 1
        reg.add("injected_defect", "FIRST_FLAG_DUPLICATED", "appointments", second["appt_key"], pk,
                "Patient has the first-appointment flag on two appointments.",
                "patients with more than one first-appointment flag", "A,17")
    change_rows = defaultdict(list)
    for c in t["appointment_change_log"]:
        change_rows[c["appt_key"]].append(c)
    for day in (date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30)):
        pool = [a for a in t["appointments"] if a["start_local"].date() == day and a["status"] == "Complete"
                and a["meds_administered"] == 1]
        a = rng.choice(pool)
        a["start_local"] = datetime.combine(day, time(20, 30))
        a["start_utc"] = to_utc(a["start_local"])
        a["updated_at"] = a["start_local"] + timedelta(hours=3)
        for c in change_rows[a["appt_key"]]:
            if c["new_status"] == "Complete":
                c["changed_at"] = a["updated_at"]
        for ad in admins_by_appt[a["appt_key"]]:
            ad["administered_at"] = a["start_local"] + timedelta(minutes=40)
        reg.add("designed_edge_case", "TIMEZONE_MONTH_BOUNDARY", "appointments", a["appt_key"], a["patient_key"],
                "Evening visit on the last day of the month: local month differs from the UTC month.",
                "month bucket by start_local vs start_utc", "A,17,19")
    recent_prog_appts = [a for a in t["appointments"] if a["status"] == "Complete" and a["meds_administered"] == 1
                         and a["therapy_key"] in PROGRAM_THERAPIES and a["start_local"].date() >= RECENT]
    for a in rng.sample(recent_prog_appts, 4):
        reg.add("injected_defect", "MISSING_SITE", "appointments", a["appt_key"], a["site_key"],
                "Mandatory site_key is blank on a treated visit.", "required fields null in dispense extract", "03,05,06")
        a["site_key"] = None

    # --- orders and status history ---------------------------------------------
    se_key = _next_key(t["order_status_events"], "status_event_key", "SE", 6)
    events_by_order = defaultdict(list)
    for e in t["order_status_events"]:
        events_by_order[e["order_key"]].append(e)
    eligible = []
    for ok, evs in sorted(events_by_order.items()):
        active = [e for e in evs if e["new_stage"] == "Active"]
        if active and orders[ok]["stage"] in ("Active", "Completed"):
            ends = [e["event_at"] for e in evs if e["new_stage"] in ("Completed", "Discontinued", "Cancelled", "On Hold")]
            limit = min(ends) if ends else CUTOFF
            if (limit - active[0]["event_at"]).days > 10:
                eligible.append((ok, active[0]["event_at"], limit))
    for i, (ok, active_at, limit) in enumerate(rng.sample(eligible, 9)):
        corrected = 1 if i >= 6 else 0
        back_at = active_at + timedelta(days=rng.randint(2, max(3, min(30, (limit - active_at).days - 3))))
        fwd_at = back_at + timedelta(hours=rng.randint(2, 20))
        e1 = dict(status_event_key=next(se_key), order_key=ok, previous_stage="Active",
                  new_stage="Benefits Verification", event_at=back_at,
                  reason="Approved correction: payer change" if corrected else None, correction_flag=corrected)
        e2 = dict(status_event_key=next(se_key), order_key=ok, previous_stage="Benefits Verification",
                  new_stage="Active", event_at=fwd_at, reason=None, correction_flag=corrected)
        t["order_status_events"] += [e1, e2]
        if corrected:
            reg.add("designed_edge_case", "BACKWARD_STAGE_CORRECTED", "order_status_events", e1["status_event_key"], ok,
                    "Backward stage move with an approved correction flag - should PASS validation.",
                    "backward transitions without correction_flag", "C,04")
        else:
            reg.add("injected_defect", "BACKWARD_STAGE", "order_status_events", e1["status_event_key"], ok,
                    "Order moved from Active back to Benefits Verification with no approved correction.",
                    "backward transitions without correction_flag", "C,04")
    prog_b_orders = {o["order_key"] for o in t["orders"] if o["therapy_key"] in C.PROGRAMS["PROGRAM_B"]["therapies"]}
    recent_b = [e for e in t["order_status_events"] if e["order_key"] in prog_b_orders
                and e["event_at"].date() >= RECENT and e["correction_flag"] == 0]
    other_ev = [e for e in t["order_status_events"] if e["order_key"] not in prog_b_orders]
    for src in rng.sample(recent_b, 3) + rng.sample(other_ev, 3):
        dup = dict(src, status_event_key=next(se_key))
        t["order_status_events"].append(dup)
        reg.add("injected_defect", "DUP_STATUS_EVENT", "order_status_events", dup["status_event_key"],
                src["status_event_key"], "Status event recorded twice (same order, stage and timestamp).",
                "duplicate status events", "C,04,05")
    no_dose_cancel = [o for o in t["orders"] if o["stage"] == "Cancelled" and o["terminal_reason"] != "Insurance denial"
                      and not treated_orders.get(o["order_key"])]
    for o in rng.sample(no_dose_cancel, 4):
        o["stage"] = "Discontinued"
        last = max(events_by_order[o["order_key"]], key=lambda e: e["event_at"])
        last["new_stage"] = "Discontinued"
        reg.add("injected_defect", "DISCONTINUED_WITHOUT_DOSE", "orders", o["order_key"], last["status_event_key"],
                "Order labelled Discontinued although no dose was ever administered (should be Cancelled).",
                "discontinued orders with zero administered visits", "C,04")
    active_multi = [o for o in t["orders"] if o["stage"] == "Active" and len(treated_orders.get(o["order_key"], [])) >= 3]
    for o in rng.sample(active_multi, 4):
        starts = sorted(treated_orders[o["order_key"]])
        arch = starts[1] + timedelta(days=2)
        o.update(stage="Discontinued", stage_updated_at=arch, archived_at=arch, terminal_reason="Patient choice")
        ev = dict(status_event_key=next(se_key), order_key=o["order_key"], previous_stage="Active",
                  new_stage="Discontinued", event_at=arch, reason="Patient choice", correction_flag=0)
        t["order_status_events"].append(ev)
        reg.add("injected_defect", "ARCHIVED_THEN_TREATED", "orders", o["order_key"], ev["status_event_key"],
                "Order archived as Discontinued, yet administered visits continue on the same order afterwards.",
                "administrations after archived_at on the same order", "C,04")
    # Place these in the Q2-Q3 2026 window so the payer scorecard's lead-time QA has something to catch.
    new_completed = [o for o in t["orders"] if o["order_type"] == "New patient" and o["stage"] in ("Completed", "Active")
                     and treated_orders.get(o["order_key"])
                     and datetime(2026, 4, 1) <= min(treated_orders[o["order_key"]]) < datetime(2026, 10, 1)]
    for o in rng.sample(new_completed, 3):
        first = min(treated_orders[o["order_key"]])
        original = o["created_at"]
        o["created_at"] = office_time(rng, first.date() + timedelta(days=rng.randint(2, 5)))
        reg.add("injected_defect", "NEGATIVE_LEAD_TIME", "orders", o["order_key"], original.isoformat(sep=" "),
                "Order created_at was overwritten after the first treatment (re-created order) - negative lead time.",
                "first treatment earlier than order creation", "B,15")

    # --- authorizations -----------------------------------------------------------
    dc_key = _next_key(t["authorization_decisions"], "decision_key", "DC", 5)
    finals = [d for d in t["authorization_decisions"] if d["decision_result"] in ("Approved", "Denied")]
    in_window = [d for d in finals if datetime(2026, 4, 1) <= d["decision_at"] < datetime(2026, 10, 1)]
    window_keys = {d["decision_key"] for d in in_window}
    for src in rng.sample(in_window, 5) + rng.sample([d for d in finals if d["decision_key"] not in window_keys], 3):
        dup = dict(src, decision_key=next(dc_key), decision_at=src["decision_at"] + timedelta(minutes=rng.randint(1, 90)))
        t["authorization_decisions"].append(dup)
        reg.add("injected_defect", "DUP_AUTH_DECISION", "authorization_decisions", dup["decision_key"], src["auth_key"],
                "Same final decision recorded twice for one request.", "decision rows per request > 1 final", "B,14")
    window = [a for a in t["authorizations"] if datetime(2026, 6, 29) <= a["requested_at"] < datetime(2026, 7, 3)
              and a["decision_at"] and a["decision_at"] > datetime(2026, 7, 6)]
    for a, stamp in zip(rng.sample(window, 3), (datetime(2026, 6, 30, 23, 55), datetime(2026, 7, 1, 0, 0),
                                                datetime(2026, 7, 1, 0, 5))):
        a["requested_at"] = stamp
        reg.add("designed_edge_case", "QUARTER_BOUNDARY", "authorizations", a["auth_key"], stamp.isoformat(sep=" "),
                "Request time sits on the Q2/Q3 boundary; quarter filters must be half-open [start, end).",
                "requests counted in exactly one quarter", "B,14")

    # --- payer history ------------------------------------------------------------
    cov_by_patient = defaultdict(list)
    for c in t["payer_history"]:
        cov_by_patient[c["patient_key"]].append(c)
    multi_cov = sorted(pk for pk, rows in cov_by_patient.items() if len(rows) >= 2)
    for pk in rng.sample(multi_cov, 5):
        first = sorted(cov_by_patient[pk], key=lambda c: c["effective_from"])[0]
        first["effective_to"] = first["effective_to"] + timedelta(days=rng.randint(10, 40))
        reg.add("injected_defect", "PAYER_INTERVAL_OVERLAP", "payer_history", first["coverage_key"], pk,
                "Coverage interval overlaps the next interval for the same patient.",
                "overlapping coverage intervals", "B,13,15")
    treated_days = defaultdict(list)
    for a in t["appointments"]:
        if a["status"] == "Complete" and a["meds_administered"] == 1:
            treated_days[a["patient_key"]].append((a["start_local"].date(), a["appt_key"]))
    gap_pool = []
    for pk in multi_cov:
        rows = sorted(cov_by_patient[pk], key=lambda c: c["effective_from"])
        for prev, c in zip(rows, rows[1:]):
            contiguous = prev["effective_to"] == c["effective_from"] - timedelta(days=1)
            hits = [(d, k) for d, k in treated_days[pk]
                    if c["effective_from"] <= d <= c["effective_from"] + timedelta(days=45)
                    and (c["effective_to"] is None or d + timedelta(days=1) <= c["effective_to"])]
            if contiguous and hits:
                gap_pool.append((pk, c, min(hits)))
                break
    for pk, c, (d, appt_key) in rng.sample(gap_pool, 4):
        c["effective_from"] = d + timedelta(days=1)
        reg.add("injected_defect", "COVERAGE_GAP", "payer_history", c["coverage_key"], appt_key,
                "A treated visit falls in a gap between coverage intervals (no payer at event).",
                "treated visits with no coverage interval", "B,13,15")
    by_umbrella = defaultdict(list)
    for c in t["payer_history"]:
        by_umbrella[plan_umbrella.get(c["plan_key"])].append(c)
    for plan_key, true_umbrella in sorted(unmapped_plans.items()):
        for c in rng.sample(by_umbrella[true_umbrella], 3):
            c["plan_key"] = plan_key
            reg.add("injected_defect", "UNMAPPED_PLAN_ALIAS", "payer_history", c["coverage_key"], plan_key,
                    "Interval uses a raw plan alias that is missing from payer_umbrella_map.",
                    "plan keys without an umbrella mapping", "B,13")

    # --- providers ----------------------------------------------------------------
    refs_by_provider = defaultdict(list)
    for r in t["referrals"]:
        refs_by_provider[r["provider_key"]].append(r)
    busy = sorted(k for k, v in refs_by_provider.items() if len(v) >= 12)
    pv_key = _next_key(t["providers"], "provider_key", "PRV", 4)
    for original in rng.sample(busy, 3):
        src = next(p for p in t["providers"] if p["provider_key"] == original)
        refs = sorted(refs_by_provider[original], key=lambda r: r["referral_at"])
        split_at = refs[len(refs) // 2]["referral_at"]
        dup = dict(src, provider_key=next(pv_key), created_date=split_at.date())
        t["providers"].append(dup)
        t["provider_specialties"].append(dict(provider_key=dup["provider_key"], specialty_code=src["primary_specialty"],
                                              is_primary=1))
        moved = 0
        for r in refs[len(refs) // 2:]:
            if rng.random() < 0.6 or moved == 0:
                r["provider_key"] = dup["provider_key"]
                moved += 1
        reg.add("injected_defect", "DUPLICATE_PROVIDER_IDENTITY", "providers", dup["provider_key"], original,
                f"Second provider record for the same source identity; {moved} later referrals point to it.",
                "providers sharing source_identity_key", "A,09,18")
    referred = {r["provider_key"] for r in t["referrals"]}
    for p in t["providers"]:
        if p["provider_key"] not in referred:
            reg.add("designed_edge_case", "NEVER_REFERRED_PROVIDER", "providers", p["provider_key"], None,
                    "Provider exists but has never referred - must not be counted as dormant.",
                    "never-referred vs dormant classification", "A,18")


def inject_inventory(t, reg):
    rng = stream("defects-inventory")
    receipts = [x for x in t["inventory_transactions"] if x["event_type"] == "RECEIPT" and x["event_at"].date() >= RECENT
                and x["qty"] % C.VIALS_PER_CARTON[x["therapy_key"]] == 0]
    x = rng.choice(receipts)
    x["unit_type"] = "CARTON"
    x["qty"] = x["qty"] // C.VIALS_PER_CARTON[x["therapy_key"]]
    reg.add("injected_defect", "INVENTORY_UNIT_MISMATCH", "inventory_transactions", x["inventory_event_key"],
            x["reference_key"], "Receipt recorded in cartons instead of vials; must be converted before reconciling.",
            "unit_type other than VIAL", "C,02,20")
    counts = [x for x in t["inventory_transactions"] if x["event_type"] == "ADJ_COUNT" and x["event_at"].date() >= RECENT]
    if len(counts) < 3:
        counts = [x for x in t["inventory_transactions"] if x["event_type"] == "ADJ_COUNT"]
    for x in rng.sample(counts, 3):
        t["inventory_transactions"].remove(x)
        snap = f"{x['site_key']}-{x['therapy_key']}-{week_start(x['event_at'].date()).isoformat()}"
        reg.add("injected_defect", "INVENTORY_UNPOSTED_ADJUSTMENT", "inventory_snapshots", snap, x["inventory_event_key"],
                f"Snapshot reflects a count adjustment of {x['qty']:+d} vial(s) that never posted to the ledger.",
                "snapshot ending_qty vs ledger bridge", "C,02,20")


def inject_licenses(t, reg):
    rng = stream("defects-licenses")
    lic = t["license_registry"]
    expired = [r for r in lic if r["expiry_date"] < C.AS_OF]
    for r in expired:
        r["recorded_status"] = "Active"
    extra = rng.choice([r for r in lic if r["expiry_date"] > C.AS_OF + timedelta(days=200)])
    extra["expiry_date"] = C.AS_OF - timedelta(days=12)
    extra["recorded_status"] = "Active"
    for r in expired + [extra]:
        reg.add("injected_defect", "LICENSE_EXPIRED_STATUS_ACTIVE", "license_registry", r["license_record_key"],
                r["staff_key"], "License is past its expiry date but still recorded as Active.",
                "expiry_date < as_of with recorded_status Active", "D,11")
    pool = [r for r in lic if r["expiry_date"] > C.AS_OF]
    picks = rng.sample(pool, 4)
    for i, r in enumerate(picks):
        t["document_index"] = [d for d in t["document_index"] if d["license_record_key"] != r["license_record_key"]]
        if i < 2:
            reg.add("injected_defect", "LICENSE_DOC_FLAG_WRONG", "license_registry", r["license_record_key"], r["staff_key"],
                    "document_flag says a document is on file, but no document exists in the index.",
                    "document_flag vs document_index presence", "D,11")
        else:
            r["document_flag"] = 0
            reg.add("injected_defect", "LICENSE_DOC_MISSING", "license_registry", r["license_record_key"], r["staff_key"],
                    "No license document on file.", "licenses without documents", "D,11")
    src = rng.choice([r for r in lic if r["credential_class"] == "RN" and r not in picks])
    dup = dict(src, license_record_key=f"LIC{len(lic) + 1:03d}")
    lic.append(dup)
    reg.add("injected_defect", "LICENSE_DUPLICATE_RECORD", "license_registry", dup["license_record_key"],
            src["license_record_key"], "Same license entered twice under two record keys.",
            "duplicate fictional_license_key", "D,11")
    sl = {(r["site_key"], r["license_type"][:3]): r for r in t["site_licenses"]}
    r = sl[("S06", "Pha")]
    r["expiry_date"] = C.AS_OF - timedelta(days=20)
    reg.add("injected_defect", "SITE_LICENSE_EXPIRED", "site_licenses", r["site_license_key"], "S06",
            "Site pharmacy permit expired.", "site licenses past expiry", "D,12")
    r = sl[("S08", "Amb")]
    r["document_flag"] = 0
    reg.add("injected_defect", "SITE_LICENSE_DOC_MISSING", "site_licenses", r["site_license_key"], "S08",
            "Site license has no document on file.", "site licenses without documents", "D,12")
    r = sl[("S02", "Pha")]
    r["expiry_date"] = C.AS_OF + timedelta(days=41)
    reg.add("designed_edge_case", "SITE_LICENSE_EXPIRING_60", "site_licenses", r["site_license_key"], "S02",
            "Site permit expires within 60 days.", "30/60/90-day renewal buckets", "D,12")
    reg.add("injected_defect", "MD_OVERLAPPING_PRIMARY", "medical_director_assignment", "MDA009|MDA010", "S08",
            "Two primary medical directors overlap at S08 (2025-09-15 to 2025-12-31).",
            "overlapping primary director intervals per site", "D,12")
    reg.add("injected_defect", "MD_SITE_UNCOVERED", "medical_director_assignment", "MDA006", "S05",
            "S05 has had no active primary medical director since 2026-09-30.",
            "sites without an active primary director as of snapshot", "D,12")


def inject_submissions(t, reg):
    rng = stream("defects-submissions")
    log = t["submission_log"]
    older = [r for r in log if r["reporting_week_start"] <= week_start(C.AS_OF) - timedelta(weeks=4)]
    picks = rng.sample(older, 7)
    for r in picks[:2]:
        r["control_record_count"] = r["output_row_count"] + 1
        reg.add("injected_defect", "CONTROL_COUNT_INCLUDES_HEADER", "submission_log", r["batch_key"], r["file_type"],
                "Control record count includes the header row (off by one).", "control count vs output rows", "C,06")
    picks[0]["ack_state"] = "Rejected"
    r = picks[2]
    prev = [x for x in log if x["program_key"] == r["program_key"] and x["file_type"] == r["file_type"]
            and x["reporting_week_start"] == r["reporting_week_start"] - timedelta(weeks=1)]
    if prev:
        r["source_row_count"], r["output_row_count"] = prev[0]["source_row_count"], prev[0]["output_row_count"]
        r["control_record_count"] = r["output_row_count"]
        reg.add("injected_defect", "WRONG_REPORTING_WEEK", "submission_log", r["batch_key"], r["file_type"],
                "File was built from the previous week's date range; counts match the wrong week.",
                "logged counts vs recomputed counts for the stated week", "C,06")
    dispense = [x for x in picks[3:] if x["file_type"] == "DISPENSE"] or [x for x in older if x["file_type"] == "DISPENSE"
                                                                          and x not in picks]
    r = dispense[0]
    r["output_row_count"] += 2
    r["control_record_count"] = r["output_row_count"]
    reg.add("injected_defect", "DUPLICATE_ROWS_IN_FILE", "submission_log", r["batch_key"], r["file_type"],
            "Two duplicate rows were left in the output file.", "logged output rows vs recomputed distinct rows", "C,06")
    rest = [x for x in older if x not in picks and x is not r]
    for x in rng.sample(rest, 2):
        x["transfer_attempts"] = 2
        x["sent_at"] = x["sent_at"] + timedelta(days=1)
        if x["acknowledged_at"]:
            x["acknowledged_at"] = x["acknowledged_at"] + timedelta(days=1)
        reg.add("designed_edge_case", "TRANSFER_RETRY", "submission_log", x["batch_key"], x["file_type"],
                "First transfer attempt failed; succeeded on retry.", "transfer_attempts > 1", "C,06")
    rest = [x for x in rest if x["transfer_attempts"] == 1]
    x = rng.choice(rest)
    x["ack_state"] = "Rejected"
    reg.add("injected_defect", "ACK_REJECTED_FORMAT", "submission_log", x["batch_key"], x["file_type"],
            "Manufacturer rejected the file for a format error.", "ack_state Rejected", "C,06")
    x = rng.choice([y for y in rest if y["ack_state"] == "Accepted"])
    x["ack_state"], x["acknowledged_at"] = "Pending", None
    reg.add("injected_defect", "ACK_STALE_PENDING", "submission_log", x["batch_key"], x["file_type"],
            "No acknowledgment received weeks after sending - needs escalation.", "ack pending > 5 business days", "C,06")
