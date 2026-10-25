"""Operational tables: drug inventory, licensing, fee schedule, targets, submissions."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from . import config as C
from .util import add_business_days, is_business_day, next_business_day, office_time, stream, week_start

PROGRAM_OF = {t: p for p, spec in C.PROGRAMS.items() for t in spec["therapies"]}
SITE_OPENED = {k: o for k, _, _, o, _ in C.SITES}
CUTOFF = datetime.combine(C.AS_OF, time(23, 59, 59))


def _dt(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def _day_in_week(wk, offset):
    """A business day inside the reporting week (never rolls into the next week)."""
    d = next_business_day(wk + timedelta(days=offset))
    if d >= wk + timedelta(days=7):
        d = wk + timedelta(days=offset)
        while not is_business_day(d) and d > wk:
            d -= timedelta(days=1)
    return d


# --------------------------------------------------------------------------
# Inventory ledger for manufacturer-program therapies
# --------------------------------------------------------------------------
def build_inventory(appointments, administrations):
    rng = stream("inventory")
    appt_site = {a["appt_key"]: a["site_key"] for a in appointments}
    events = defaultdict(list)            # (site, therapy) -> [(when, type, qty, ref, lot)]
    for ad in administrations:
        if ad["therapy_key"] not in PROGRAM_OF:
            continue
        cell = (appt_site[ad["appt_key"]], ad["therapy_key"])
        etype = "ADMINISTERED" if ad["administered_flag"] == 1 else "ADJ_WASTE"
        events[cell].append((ad["administered_at"], etype, -ad["vials"], ad["admin_key"], ad["lot_code"]))

    first_week = week_start(C.DATA_START)
    last_week = week_start(C.AS_OF)
    tx, snapshots, purchase_orders = [], [], []
    po_n = 0
    for site_key, *_ in C.SITES:
        for therapy_key in PROGRAM_OF:
            cell = (site_key, therapy_key)
            demand = sorted(events.get(cell, []), key=lambda e: e[0])
            open_week = max(first_week, week_start(SITE_OPENED[site_key]))
            carton = C.VIALS_PER_CARTON[therapy_key]
            on_hand = carton * rng.randint(1, 3)
            weekly_use = defaultdict(int)
            for when, etype, qty, *_ in demand:
                weekly_use[week_start(when.date())] -= qty
            di = 0
            wk = open_week
            while wk <= last_week:
                begin = on_hand
                week_events = []
                trailing = [weekly_use.get(wk - timedelta(weeks=k), 0) for k in range(1, 9)]
                avg_use = max(1.0, sum(trailing) / 8)
                if on_hand < 2.5 * avg_use:
                    need = 5 * avg_use - on_hand
                    cartons = max(1, int(-(-need // carton)))
                    recv_day = _day_in_week(wk, rng.randint(1, 3))
                    po_n += 1
                    po_key = f"PO{po_n:05d}"
                    ordered = office_time(rng, add_business_days(recv_day, -rng.randint(2, 5)))
                    received = office_time(rng, recv_day, 8, 11)
                    purchase_orders.append(dict(po_key=po_key, site_key=site_key, therapy_key=therapy_key,
                                                ordered_at=ordered, received_at=received,
                                                cartons=cartons, qty_vials=cartons * carton))
                    week_events.append((received, "RECEIPT", cartons * carton, po_key, None))
                # Occasional adjustments
                if rng.random() < 0.02 and on_hand > 2:
                    week_events.append((office_time(rng, _day_in_week(wk, 4)), "ADJ_EXPIRED",
                                        -rng.randint(1, 2), None, None))
                if rng.random() < 0.02:
                    week_events.append((office_time(rng, _day_in_week(wk, 4)), "ADJ_COUNT",
                                        rng.choice([-1, 1]), None, None))
                if rng.random() < 0.006:
                    week_events.append((office_time(rng, _day_in_week(wk, 2)), "RETURN_IN",
                                        1, None, None))
                wk_end = wk + timedelta(days=7)
                while di < len(demand) and demand[di][0].date() < wk_end:
                    week_events.append(demand[di])
                    di += 1
                week_events.sort(key=lambda e: e[0])
                for when, etype, qty, ref, lot in week_events:
                    if on_hand + qty < 0:          # emergency carton before the shortfall
                        po_n += 1
                        po_key = f"PO{po_n:05d}"
                        rec_at = when - timedelta(hours=2)
                        purchase_orders.append(dict(po_key=po_key, site_key=site_key, therapy_key=therapy_key,
                                                    ordered_at=rec_at - timedelta(days=1), received_at=rec_at,
                                                    cartons=1, qty_vials=carton))
                        tx.append(dict(site_key=site_key, therapy_key=therapy_key, event_at=rec_at,
                                       event_type="RECEIPT", qty=carton, unit_type="VIAL",
                                       reference_key=po_key, lot_code=None))
                        on_hand += carton
                    on_hand += qty
                    tx.append(dict(site_key=site_key, therapy_key=therapy_key, event_at=when, event_type=etype,
                                   qty=qty, unit_type="VIAL", reference_key=ref, lot_code=lot))
                snapshots.append(dict(site_key=site_key, therapy_key=therapy_key, week_start=wk,
                                      beginning_qty=begin, ending_qty=on_hand,
                                      snapshot_taken_at=datetime.combine(wk_end, time(1, 15)) if wk < last_week else CUTOFF))
                wk = wk_end
    tx.sort(key=lambda r: (r["event_at"], r["site_key"], r["therapy_key"], r["event_type"]))
    for i, r in enumerate(tx, 1):
        r["inventory_event_key"] = f"IE{i:06d}"
    for r in snapshots:
        r["snapshot_key"] = f"{r['site_key']}-{r['therapy_key']}-{r['week_start'].isoformat()}"
    return tx, snapshots, purchase_orders


# --------------------------------------------------------------------------
# Licensing: staff credentials, site licenses, medical-director coverage
# --------------------------------------------------------------------------
def build_licenses():
    rng = stream("licenses")
    mix = [("RN", 29), ("LPN", 4), ("APRN", 4), ("PharmD", 3), ("MD", 4)]
    role = {"RN": "Registered nurse", "LPN": "Licensed practical nurse", "APRN": "Nurse practitioner",
            "PharmD": "Pharmacist", "MD": "Physician / medical director"}
    site_keys = [s[0] for s in C.SITES]
    site_state = {s[0]: next(c[2] for c in C.COUNTIES if c[0] == s[2]) for s in C.SITES}
    # Expiry offsets (days from AS_OF) chosen so every renewal bucket is populated.
    offsets = ([-45] + [rng.randint(3, 29) for _ in range(3)] + [rng.randint(31, 59) for _ in range(3)]
               + [rng.randint(61, 89) for _ in range(4)] + [rng.randint(95, 730) for _ in range(33)])
    rng.shuffle(offsets)
    staff, licenses, docs = [], [], []
    n = 0
    used = set()
    for cls, count in mix:
        for _ in range(count):
            n += 1
            staff_key = f"STF{n:03d}"
            site = rng.choice(site_keys)
            state = site_state[site]
            staff.append(dict(staff_key=staff_key, staff_label=f"{cls}-{n:03d} (fictional)", role=role[cls],
                              home_site_key=site, employment_status="Active",
                              hire_date=date(2018, 1, 1) + timedelta(days=rng.randrange(0, 3000))))
            expiry = C.AS_OF + timedelta(days=offsets[n - 1])
            term_years = 2 if cls in ("RN", "LPN", "APRN", "PharmD") else 2
            issue = expiry - timedelta(days=365 * term_years)
            while True:
                lic = f"MOCK-{cls}-{state}-{rng.randrange(10000, 99999)}"
                if lic not in used:
                    used.add(lic)
                    break
            scope = "Multistate (compact, mock)" if cls in ("RN", "LPN") and rng.random() < 0.6 else "Single-state"
            status = "Expired" if expiry < C.AS_OF else "Active"
            licenses.append(dict(license_record_key=f"LIC{n:03d}", staff_key=staff_key, fictional_license_key=lic,
                                 credential_class=cls, license_scope=scope, state_code=state, issue_date=issue,
                                 expiry_date=expiry, verified_date=issue + timedelta(days=rng.randint(1, 40)),
                                 recorded_status=status, document_flag=1))
            docs.append(dict(document_key=f"DOC{n:03d}", license_record_key=f"LIC{n:03d}",
                             document_placeholder=f"placeholder_license_{n:03d}.pdf",
                             document_type="License verification printout (mock)",
                             uploaded_at=office_time(rng, issue + timedelta(days=rng.randint(1, 45)))))

    site_licenses = []
    m = 0
    for site_key, *_ in C.SITES:
        for ltype, prefix in (("Ambulatory infusion center license (mock)", "AIC"), ("Pharmacy permit (mock)", "PHA")):
            m += 1
            expiry = C.AS_OF + timedelta(days=rng.randint(100, 700))
            site_licenses.append(dict(site_license_key=f"SLC{m:03d}", site_key=site_key, license_type=ltype,
                                      fictional_license_key=f"MOCK-{prefix}-{site_state[site_key]}-{rng.randrange(1000, 9999)}",
                                      state_code=site_state[site_key], issue_date=expiry - timedelta(days=730),
                                      expiry_date=expiry, document_flag=1))

    directors = [s["staff_key"] for s in staff if s["role"].startswith("Physician")]
    d1, d2, d3, d4 = directors
    md = [
        ("S01", d1, date(2019, 3, 4), None), ("S02", d2, date(2020, 6, 1), None),
        ("S03", d1, date(2022, 1, 10), date(2025, 6, 30)), ("S03", d3, date(2025, 7, 1), None),
        ("S04", d2, date(2018, 9, 17), None), ("S05", d4, date(2021, 4, 5), date(2026, 9, 30)),
        ("S06", d3, date(2023, 2, 6), None), ("S07", d4, date(2019, 11, 4), None),
        ("S08", d3, date(2025, 9, 15), None), ("S08", d1, date(2025, 9, 1), date(2025, 12, 31)),
    ]
    assignments = [dict(assignment_key=f"MDA{i:03d}", site_key=s, director_staff_key=d, relationship_start=a,
                        relationship_end=b, is_primary=1) for i, (s, d, a, b) in enumerate(md, 1)]
    return staff, licenses, docs, site_licenses, assignments


# --------------------------------------------------------------------------
# Mock fee schedule (revenue-operations reference data)
# --------------------------------------------------------------------------
def build_fee_schedule():
    rng = stream("fees")
    therapy_codes = {t["mock_code"]: k for k, t in C.THERAPIES.items()}
    codes = [f"XJ{n}" for n in range(101, 161)] + [f"XQ{n}" for n in range(201, 211)]
    catalog, schedule = [], []
    # Sorted lists, not sets: set order changes between runs and would break reproducibility.
    zero_pay = sorted(rng.sample(codes[12:], 6))
    facility_only = sorted(rng.sample([c for c in codes[12:] if c not in zero_pay], 5))
    rate_change = sorted(rng.sample([c for c in codes if c not in zero_pay], 20))
    r = 0
    for code in codes:
        catalog.append(dict(mock_code=code, code_description=f"Mock drug/supply code {code} (fictional)",
                            billing_unit="per unit (mock)", therapy_key=therapy_codes.get(code)))
        claim_type = "Facility" if code in facility_only else "Professional"
        base = 0.0 if code in zero_pay else round(rng.uniform(18, 4800), 2)
        note = "Zero-pay (non-covered, mock)" if code in zero_pay else "Fixed (mock)"
        if code in rate_change:
            r += 1
            schedule.append(dict(fee_row_key=f"FS{r:03d}", mock_code=code, claim_type=claim_type,
                                 effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31),
                                 fictional_fee_amount=base, pricing_note=note))
            r += 1
            schedule.append(dict(fee_row_key=f"FS{r:03d}", mock_code=code, claim_type=claim_type,
                                 effective_from=date(2026, 1, 1), effective_to=None,
                                 fictional_fee_amount=round(base * rng.uniform(0.94, 1.08), 2), pricing_note=note))
        else:
            r += 1
            schedule.append(dict(fee_row_key=f"FS{r:03d}", mock_code=code, claim_type=claim_type,
                                 effective_from=date(2025, 1, 1) if rng.random() < 0.85 else date(2026, 4, 1),
                                 effective_to=None, fictional_fee_amount=base, pricing_note=note))
    # Lookup requests an analyst would receive (some deliberately tricky).
    requests = []
    not_on_schedule = [f"XJ{n}" for n in range(161, 169)]
    for code in not_on_schedule:
        catalog.append(dict(mock_code=code, code_description=f"Mock drug/supply code {code} (fictional)",
                            billing_unit="per unit (mock)", therapy_key=None))
    pool = (rng.sample(codes, 40) + not_on_schedule + facility_only + zero_pay[:4])
    rng.shuffle(pool)
    for i, code in enumerate(pool, 1):
        svc = date(2025, 1, 1) + timedelta(days=rng.randrange(0, (C.AS_OF - date(2025, 1, 1)).days))
        requests.append(dict(request_key=f"LR{i:03d}", mock_code=code, claim_type_requested="Professional",
                             service_date=svc, batch_key="BATCH-2026-10"))
    for code in rng.sample(codes, 3):          # service dates before a late effective_from
        i = len(requests) + 1
        requests.append(dict(request_key=f"LR{i:03d}", mock_code=code, claim_type_requested="Professional",
                             service_date=date(2024, 11, 15), batch_key="BATCH-2026-10"))
    dup = requests[4]
    requests.append(dict(dup, request_key=f"LR{len(requests) + 1:03d}"))
    return catalog, schedule, requests


# --------------------------------------------------------------------------
# Monthly appointment goals per site (for the refresh/goals case study)
# --------------------------------------------------------------------------
def build_targets(appointments):
    rng = stream("targets")
    done = defaultdict(int)
    for a in appointments:
        if a["status"] == "Complete" and a["site_key"]:
            d = _dt(a["start_local"]).date()
            if date(2025, 7, 1) <= d <= date(2025, 12, 31):
                done[a["site_key"]] += 1
    rows = []
    for site_key, *_ in C.SITES:
        base = done.get(site_key, 0) / 6
        for month in range(1, 13):
            if site_key == "S08":
                goal = 20 + 6 * month
            else:
                goal = base * (1.0 + 0.012 * month) * rng.uniform(0.97, 1.05)
            rows.append(dict(site_key=site_key, target_month=date(2026, month, 1),
                             completed_appointment_goal=int(round(goal / 5) * 5)))
    return rows


# --------------------------------------------------------------------------
# Manufacturer submission log (what was logged at send time)
# --------------------------------------------------------------------------
def submission_counts(tables, week, generated_at):
    """Row counts each program file would have had when it was generated."""
    wk_end = week + timedelta(days=7)
    appt = {a["appt_key"]: a for a in tables["appointments"]}
    counts = {}
    for program, spec in C.PROGRAMS.items():
        therapies = set(spec["therapies"])
        lines = []
        for ad in tables["administrations"]:
            if ad["therapy_key"] not in therapies or ad["administered_flag"] != 1:
                continue
            a = appt[ad["appt_key"]]
            start = _dt(a["start_local"])
            if week <= start.date() < wk_end and _dt(a["updated_at"]) <= generated_at:
                lines.append((ad["appt_key"], ad["therapy_key"]))
        counts[(program, "DISPENSE")] = (len(lines), len(set(lines)))
        tx = [t for t in tables["inventory_transactions"] if t["therapy_key"] in therapies
              and week <= _dt(t["event_at"]).date() < wk_end]
        cells = len([s for s in tables["inventory_snapshots"] if s["therapy_key"] in therapies and s["week_start"] == week])
        counts[(program, "INVENTORY")] = (len(tx), cells)
        if "STATUS" in spec["files"]:
            order_therapy = {o["order_key"]: o["therapy_key"] for o in tables["orders"]}
            ev = [(e["order_key"], e["new_stage"], _dt(e["event_at"]).date()) for e in tables["order_status_events"]
                  if order_therapy.get(e["order_key"]) in therapies and week <= _dt(e["event_at"]).date() < wk_end
                  and _dt(e["event_at"]) <= generated_at]
            counts[(program, "STATUS")] = (len(ev), len(set(ev)))
    return counts


def build_submission_log(tables, n_weeks=24):
    rng = stream("submissions")
    last_week = week_start(C.AS_OF) - timedelta(weeks=1)   # last complete week
    weeks = [last_week - timedelta(weeks=k) for k in range(n_weeks - 1, -1, -1)]
    rows = []
    n = 0
    for week in weeks:
        gen_day = next_business_day(week + timedelta(days=8 + rng.randint(0, 1)))
        generated_at = office_time(rng, gen_day, 9, 12)
        counts = submission_counts(tables, week, generated_at)
        for (program, file_type), (source, output) in counts.items():
            n += 1
            sent = generated_at + timedelta(hours=rng.randint(1, 4))
            ack = sent + timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 6))
            rows.append(dict(batch_key=f"SB{n:04d}", program_key=program, file_type=file_type,
                             reporting_week_start=week, generated_at=generated_at,
                             source_row_count=source, output_row_count=output, control_record_count=output,
                             operator_qa_state="Passed", transfer_status="Sent", transfer_attempts=1,
                             sent_at=sent, ack_state="Accepted" if ack <= CUTOFF else "Pending",
                             acknowledged_at=ack if ack <= CUTOFF else None,
                             destination="mock://manufacturer-" + program[-1].lower() + "/inbound"))
    return rows
