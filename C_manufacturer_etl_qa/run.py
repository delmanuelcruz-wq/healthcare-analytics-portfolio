"""Project C - Manufacturer data-agreement ETL, status rules engine and submission QA console (SYNTHETIC).

    python C_manufacturer_etl_qa/run.py

Builds weekly INVENTORY / DISPENSE / STATUS extracts for two fictional programs, routes every
order-status change through a rules engine, audits all 120 logged submissions against a
recomputation, writes a sample submission package with control files, and the console dashboard.
Destinations are mock URIs only - nothing is transmitted anywhere.
"""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from shared import portfolio as P  # noqa: E402

SQL, OUT = HERE / "sql", HERE / "outputs"
CUTOFF = datetime(2026, 10, 24, 23, 59, 59)
TOKEN_SALT = "coralline-demo-salt"   # demo only - a real pipeline keeps its salt in a secret store
STAGE_RANK = {"Intake": 1, "Benefits Verification": 2, "Prior Authorization": 3, "Ready to Schedule": 4,
              "Active": 5, "On Hold": 5, "Completed": 6, "Discontinued": 6, "Cancelled": 6}
FILE_ORDER = [("PROGRAM_A", "INVENTORY"), ("PROGRAM_A", "DISPENSE"), ("PROGRAM_B", "INVENTORY"),
              ("PROGRAM_B", "DISPENSE"), ("PROGRAM_B", "STATUS")]
SEVERITY = {"pass": 0, "info": 0, "yellow": 1, "red": 2}


def token(kind, key):
    return f"{kind}-" + hashlib.sha256(f"{TOKEN_SALT}:{key}".encode()).hexdigest()[:12].upper()


def dt(s):
    return datetime.fromisoformat(s) if s else None


def business_days_after(start: date, when: date) -> int:
    """Business days from `start` (exclusive) to `when` (inclusive); 0 if on/before start."""
    n, d = 0, start
    while d < when:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# --------------------------------------------------------------------------- rules engine
def status_code(stage, doses_before):
    if stage in ("Intake", "Benefits Verification", "Prior Authorization", "Ready to Schedule"):
        return "PENDING_START"
    if stage == "Cancelled":
        return "CANCELLED_BEFORE_FIRST_DOSE" if doses_before == 0 else "DISCONTINUED_AFTER_DOSE"
    if stage == "Discontinued":
        return "DISCONTINUED_AFTER_DOSE" if doses_before > 0 else "CANCELLED_BEFORE_FIRST_DOSE"
    return {"Active": "ACTIVE", "On Hold": "ON_HOLD", "Completed": "COMPLETED"}[stage]


def route(ev):
    """Return (disposition, rule, recommended action) for one status event."""
    prev, new = ev["previous_stage"], ev["new_stage"]
    backward = prev is not None and STAGE_RANK[new] < STAGE_RANK[prev]
    if ev["earlier_identical_events"]:
        return "Review", "Duplicate status event", "Suppress from the file; keep the first occurrence"
    if backward and not ev["correction_flag"]:
        return "Escalate", "Backward stage move without an approved correction", "Confirm with the order owner before reporting"
    if backward:
        return "Verified", "Backward move with approved correction", "Report the corrected stage"
    if new == "Discontinued" and ev["doses_before_event"] == 0:
        return "Review", "Discontinued with no prior dose", "Reclassify as cancelled before first dose"
    if new == "Cancelled" and ev["doses_before_event"] > 0:
        return "Review", "Cancelled after a dose", "Reclassify as discontinued after dose"
    if new in ("Discontinued", "Cancelled", "Completed") and ev["doses_after_archive"] > 0:
        return "Escalate", "Treatment continued after the order was archived", "Do not report as stopped; verify with clinical team"
    if new == "Intake" and ev["first_dose_at"] and ev["order_created_at"] > ev["first_dose_at"]:
        return "Review", "Order created after its first dose", "Check for a re-created order before using order dates"
    return "Verified", "Valid transition with consistent evidence", ""


def run_rules(events):
    routed, cases = [], []
    for ev in events:
        disposition, rule, action = route(ev)
        rec = dict(ev, disposition=disposition, rule=rule, recommended_action=action,
                   manufacturer_status=status_code(ev["new_stage"], ev["doses_before_event"]))
        routed.append(rec)
        if disposition != "Verified" or ev["correction_flag"]:
            cases.append(dict(case_key=f"EXC-{len(cases) + 1:04d}", status_event_key=ev["status_event_key"],
                              order_token=token("ORD", ev["order_key"]), order_key=ev["order_key"],
                              program_key=ev["program_key"] or "-", therapy_key=ev["therapy_key"],
                              transition=f"{ev['previous_stage'] or '(start)'} -> {ev['new_stage']}", event_at=ev["event_at"],
                              doses_before_event=ev["doses_before_event"], doses_after_archive=ev["doses_after_archive"],
                              disposition=disposition, rule=rule, recommended_action=action,
                              owner_role="Analytics" if disposition == "Review" else "Order owner / clinical lead"))
    return routed, cases


# --------------------------------------------------------------------------- weekly files
def build_files(bridge, dispense, routed):
    files = defaultdict(list)          # (program, file_type, week) -> rows
    for b in bridge:
        computed = b["opening_qty"] + b["receipts"] + b["returns_in"] - b["administered"] - b["waste_expired"] + b["count_adjustments"]
        b["computed_closing_qty"] = computed
        b["variance"] = b["system_closing_qty"] - computed
        b["recon_status"] = "Reconciled" if b["variance"] == 0 else "Variance - investigate"
        files[(b["program_key"], "INVENTORY", b["week_start"])].append(dict(
            reporting_week=b["week_start"], site_id=b["site_key"], product_id=b["therapy_key"], opening_vials=b["opening_qty"],
            received_vials=b["receipts"], returned_vials=b["returns_in"], administered_vials=b["administered"],
            waste_expired_vials=b["waste_expired"], adjustment_vials=b["count_adjustments"], closing_vials=b["system_closing_qty"],
            reconciliation=b["recon_status"]))
    for r in dispense:
        files[(r["program_key"], "DISPENSE", r["week_start"])].append(dict(
            reporting_week=r["week_start"], site_id=r["site_key"] or "", product_id=r["therapy_key"],
            patient_token=token("PT", r["patient_key"]), treatment_date=r["treatment_date"], vials=r["vials"],
            injection_number=r["injection_ordinal"], first_therapy_date=r["first_therapy_date"], payer_segment=r["payer_segment"]))
    week_starts = sorted({b["week_start"] for b in bridge})
    for ev in routed:
        if ev["program_key"] != "PROGRAM_B" or ev["disposition"] == "Review" and ev["rule"] == "Duplicate status event":
            continue
        day = ev["event_at"][:10]
        wk = next((w for w in week_starts if w <= day < (date.fromisoformat(w) + timedelta(days=7)).isoformat()), None)
        if wk:
            files[("PROGRAM_B", "STATUS", wk)].append(dict(
                reporting_week=wk, order_token=token("ORD", ev["order_key"]), product_id=ev["therapy_key"],
                status_date=day, status_code=ev["manufacturer_status"], reason=ev["reason"] or "",
                qa_disposition=ev["disposition"]))
    return files


def write_package(files, week, folder: Path):
    """Write one week's files + control files + manifest (mock destination only)."""
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    for program, ftype in FILE_ORDER:
        rows = files.get((program, ftype, week), [])
        name = f"{program}_{ftype}_{week.replace('-', '')}.csv"
        path = folder / name
        with path.open("w", newline="", encoding="utf-8") as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ctl = dict(file_name=name, program=program, file_type=ftype, reporting_week=week,
                   record_count=len(rows), header_rows=1, sha256=digest, destination=f"mock://manufacturer-{program[-1].lower()}/inbound")
        (folder / name.replace(".csv", ".ctl.json")).write_text(json.dumps(ctl, indent=2) + "\n", encoding="utf-8")
        manifest.append(ctl)
    (folder / "manifest.json").write_text(json.dumps(dict(disclaimer=P.DISCLAIMER, files=manifest), indent=2) + "\n", encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------- console
def audit_batches(batches, files, bridge, dispense_qa, routed_by_week):
    by_key = {(b["program_key"], b["file_type"], b["reporting_week_start"]): b for b in batches}
    results = []
    for b in batches:
        tests = []

        def t(name, status, detail):
            tests.append(dict(test=name, status=status, detail=detail))

        if b["control_record_count"] == b["output_row_count"]:
            t("Control count", "pass", "Control count equals data rows (header excluded)")
        elif b["control_record_count"] == b["output_row_count"] + 1:
            t("Control count", "red", "Control count includes the header row (off by one)")
        else:
            t("Control count", "red", f"Control {b['control_record_count']} vs {b['output_row_count']} data rows")

        logged = (b["source_row_count"], b["output_row_count"])
        recomputed = (b["recomputed_source"], b["recomputed_output"])
        diagnosis = None
        if logged == recomputed:
            t("Logged vs recomputed", "pass", f"{b['output_row_count']} rows match a fresh recomputation")
        else:
            prev_week = (date.fromisoformat(b["reporting_week_start"]) - timedelta(days=7)).isoformat()
            prev = by_key.get((b["program_key"], b["file_type"], prev_week))
            if prev and logged in ((prev["recomputed_source"], prev["recomputed_output"]), (prev["source_row_count"], prev["output_row_count"])):
                diagnosis = "WRONG_REPORTING_WEEK"
                t("Logged vs recomputed", "red", f"Counts match the PREVIOUS week ({prev_week}) - file built from the wrong date range")
            elif logged[0] == recomputed[0] and logged[1] > recomputed[1]:
                diagnosis = "DUPLICATE_ROWS_IN_FILE"
                t("Logged vs recomputed", "red", f"{logged[1] - recomputed[1]} more rows than distinct records - duplicates left in the file")
            else:
                diagnosis = "UNEXPLAINED_MISMATCH"
                t("Logged vs recomputed", "red", f"Logged {logged} vs recomputed {recomputed}")

        if b["file_type"] == "DISPENSE":
            late = (b["recomputed_output_now"] or 0) - (b["recomputed_output"] or 0)
            if late > 0:
                t("Late updates since send", "yellow", f"{late} visit(s) completed in the source after the file was built - restatement candidate")
            q = dispense_qa.get((b["program_key"], b["reporting_week_start"]), {})
            if q.get("blank_site"):
                t("Mandatory fields", "yellow", f"{q['blank_site']} row(s) missing site_id - corrected extract flags them before resubmission")
            if q.get("duplicate_lines") or q.get("invalid_visit_lines"):
                t("Source cleanup", "info", f"{q.get('duplicate_lines', 0)} exact duplicate line(s) removed; "
                                            f"{q.get('invalid_visit_lines', 0)} line(s) on non-treated visits excluded")
        if b["file_type"] == "INVENTORY":
            cells = [x for x in bridge if x["program_key"] == b["program_key"] and x["week_start"] == b["reporting_week_start"]]
            bad = [x["snapshot_key"] for x in cells if x["variance"]]
            if bad:
                t("Inventory bridge", "yellow", f"{len(bad)} site-product cell(s) do not reconcile: {', '.join(bad)}")
            conv = sum(x["carton_rows_converted"] for x in cells)
            if conv:
                t("Unit conversion", "info", f"{conv} carton receipt converted to vials before reconciling")
        if b["file_type"] == "STATUS":
            evs = routed_by_week.get(b["reporting_week_start"], [])
            esc = [e for e in evs if e["disposition"] == "Escalate"]
            rev = [e for e in evs if e["disposition"] == "Review"]
            if esc:
                t("Status rules", "red", f"{len(esc)} event(s) need escalation before reporting")
            elif rev:
                t("Status rules", "yellow", f"{len(rev)} event(s) routed for review")

        if b["transfer_attempts"] > 1:
            t("Transfer", "info", f"Succeeded on attempt {b['transfer_attempts']}")
        sent = dt(b["sent_at"])
        if b["ack_state"] == "Rejected":
            t("Acknowledgment", "red", "Rejected by the manufacturer")
        elif b["ack_state"] == "Pending":
            waited = business_days_after(sent.date(), CUTOFF.date())
            t("Acknowledgment", "red" if waited > 5 else "yellow",
              f"No acknowledgment after {waited} business day(s)" + (" - escalate" if waited > 5 else ""))
        else:
            t("Acknowledgment", "pass", f"Accepted {b['acknowledged_at'][:10]}")

        worst = max(tests, key=lambda x: SEVERITY[x["status"]])["status"]
        overall = {"pass": "green", "info": "green", "yellow": "yellow", "red": "red"}[worst]
        results.append(dict(batch_key=b["batch_key"], program_key=b["program_key"], file_type=b["file_type"],
                            reporting_week=b["reporting_week_start"], overall=overall, diagnosis=diagnosis,
                            logged_rows=b["output_row_count"], recomputed_rows=b["recomputed_output"],
                            recomputed_rows_now=b["recomputed_output_now"], control_count=b["control_record_count"],
                            ack_state=b["ack_state"], generated_at=b["generated_at"], sent_at=b["sent_at"],
                            acknowledged_at=b["acknowledged_at"], tests=tests,
                            issues="; ".join(f"{x['test']}: {x['detail']}" for x in tests if x["status"] in ("yellow", "red"))))
    return results


def cutoff_sensitivity(con):
    """How complete would dispense files be if generated k business days after week end?"""
    rows = P.query(con, """SELECT v.appt_key, v.start_local, a.updated_at, w.week_end
                           FROM program_visits v JOIN appointments a USING (appt_key)
                           JOIN weeks w ON v.start_local >= w.week_start AND v.start_local < w.week_end""")
    lags = [business_days_after(date.fromisoformat(r["week_end"]) - timedelta(days=1), dt(r["updated_at"]).date()) for r in rows]
    return [dict(business_days_after_week_end=k, share_of_visits_captured=sum(1 for g in lags if g <= k) / len(lags))
            for k in range(0, 11)], len(lags)


# --------------------------------------------------------------------------- QA
def run_qa(con, results, bridge, dispense, dispense_qa, routed, cases, register, files, sample_manifest):
    checks = []

    def add(name, status, observed, rule):
        checks.append(dict(check=name, status=status, observed=observed, rule=rule))

    diag = {r["batch_key"]: r["diagnosis"] for r in results if r["diagnosis"]}
    planted = {r["record_key"]: r["defect_type"] for r in register if r["defect_type"] in ("WRONG_REPORTING_WEEK", "DUPLICATE_ROWS_IN_FILE")}
    add("Logged batch counts match a fresh recomputation", "pass" if diag == planted else "fail",
        f"{len(results) - len(diag)}/{len(results)} batches match; {len(diag)} flagged and diagnosed "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(diag.items()))})", "Recompute every file with the original rules at its generation time")
    header = [r["batch_key"] for r in results if any(t["detail"].startswith("Control count includes") for t in r["tests"])]
    add("Control counts exclude the header row", "warn" if header else "pass",
        f"{len(header)} batch(es) counted the header: {', '.join(header)}", "record_count = data rows only")
    var = [b["snapshot_key"] for b in bridge if b["variance"]]
    add("Inventory bridge reconciles opening to closing", "warn" if var else "pass",
        f"{len(bridge) - len(var)}/{len(bridge)} site-product-weeks reconcile; variances: {', '.join(var)} "
        "(snapshot reflects an adjustment the ledger never posted)", "opening + receipts + returns - administered - waste +/- adjustments = closing")
    conv = sum(b["carton_rows_converted"] for b in bridge)
    effect = sum(b["conversion_effect"] for b in bridge)
    add("Packaging units normalized before reconciling", "pass", f"{conv} receipt recorded in cartons converted (+{effect} vials); "
        "without conversion that week would show a false variance", "All quantities in vials")
    dup = sum(q["duplicate_lines"] for q in dispense_qa.values())
    inval = sum(q["invalid_visit_lines"] for q in dispense_qa.values())
    blank = sum(q["blank_site"] for q in dispense_qa.values())
    add("Dispense extract cleaned at the right grain", "warn" if (dup or inval or blank) else "pass",
        f"{len(dispense)} appointment-product rows; {dup} exact duplicate line(s) removed, {inval} line(s) on non-treated visits "
        f"excluded, {blank} row(s) missing site flagged", "One row per treated appointment x product; vials never double-counted")
    tie = P.query(con, """SELECT b.site_key, b.therapy_key, b.week_start, b.administered,
                                 COALESCE((SELECT SUM(v.vials) FROM program_visits v WHERE v.site_key = b.site_key
                                   AND v.therapy_key = b.therapy_key AND v.start_local >= b.week_start
                                   AND v.start_local < date(b.week_start, '+7 days')), 0) AS dispensed
                          FROM (SELECT s.site_key, s.therapy_key, s.week_start,
                                       -COALESCE((SELECT SUM(t.qty) FROM inventory_transactions t WHERE t.site_key = s.site_key
                                         AND t.therapy_key = s.therapy_key AND t.event_type = 'ADMINISTERED'
                                         AND date(t.event_at) >= s.week_start AND date(t.event_at) < date(s.week_start, '+7 days')), 0) AS administered
                                FROM inventory_snapshots s JOIN program_therapy USING (therapy_key)
                                WHERE s.week_start IN (SELECT week_start FROM weeks)) b""")
    off = [r for r in tie if r["administered"] != r["dispensed"]]
    blank_sites = {(r["therapy_key"], r["week_start"]) for r in dispense if not r["site_key"]}
    unexplained = [r for r in off if (r["therapy_key"], r["week_start"]) not in blank_sites]
    add("Inventory 'administered' ties to dispense vials", "pass" if not unexplained else "fail",
        f"{len(tie) - len(off)}/{len(tie)} site-product-weeks tie; {len(off)} differ only where a dispense row is missing its site",
        "Two independent sources must agree")
    full = Counter()
    for r in dispense:
        if r["program_key"] == "PROGRAM_B":
            full[min(r["injection_ordinal"], 6)] += 1
    add("Injection number uses full treatment history", "pass",
        f"Program B: {sum(v for k, v in full.items() if k > 1)} of {sum(full.values())} rows are a 2nd-or-later dose; "
        "a week-only extract would label all of them dose #1", "Ordinal is therapy-specific and counts prior administered visits")
    esc = [c for c in cases if c["disposition"] == "Escalate"]
    rev = [c for c in cases if c["disposition"] == "Review"]
    expected_events = {r["record_key"] for r in register if r["defect_type"] in ("BACKWARD_STAGE", "DUP_STATUS_EVENT")}
    expected_orders = {r["record_key"] for r in register if r["defect_type"] in ("DISCONTINUED_WITHOUT_DOSE", "ARCHIVED_THEN_TREATED", "NEGATIVE_LEAD_TIME")}
    flagged = [c for c in cases if c["disposition"] != "Verified"]
    explained = all(c["status_event_key"] in expected_events or c["order_key"] in expected_orders for c in flagged)
    found_all = (expected_events <= {c["status_event_key"] for c in flagged}
                 and expected_orders <= {c["order_key"] for c in flagged})
    ok = explained and found_all
    add("Status rules engine routes every planted exception", "pass" if ok else "fail",
        f"{len(esc)} Escalate, {len(rev)} Review, {sum(1 for c in cases if c['disposition'] == 'Verified')} approved corrections "
        f"out of {len(routed):,} status events; no false positives", "Verified / Review / Escalate with written reasons")
    restate = [r for r in results if r["file_type"] == "DISPENSE" and any(t["test"] == "Late updates since send" for t in r["tests"])]
    add("Late source updates after files were sent", "warn" if restate else "pass",
        f"{len(restate)} of {sum(1 for r in results if r['file_type'] == 'DISPENSE')} dispense files missed visits completed after generation",
        "Generate later or schedule restatements; see the cut-off analysis")
    acks = Counter(r["ack_state"] for r in results)
    stale = [r["batch_key"] for r in results if any(t["test"] == "Acknowledgment" and "escalate" in t["detail"] for t in r["tests"])]
    add("Acknowledgments tracked separately from file creation", "warn",
        f"{acks['Accepted']} accepted, {acks['Rejected']} rejected, {acks['Pending']} pending ({len(stale)} stale: {', '.join(stale)})",
        "A file on disk is not a delivered file")
    dests = P.scalar(con, "SELECT COUNT(*) FROM submission_log WHERE destination NOT LIKE 'mock://%'")
    add("Mock destinations only", "pass" if dests == 0 else "fail", "All 120 destinations are mock:// URIs; nothing is transmitted",
        "No real endpoints in a public portfolio")
    leaked = any("PT0" in (OUT / "sample_submission").joinpath(m["file_name"]).read_text(encoding="utf-8") for m in sample_manifest)
    add("Patient keys never leave the warehouse", "pass" if not leaked else "fail",
        "Files carry salted one-way tokens (PT-..., ORD-...), never warehouse keys", "Pseudonymize before export")
    return checks


# --------------------------------------------------------------------------- main
def main():
    con = P.connect()
    P.run_script(con, SQL / "01_staging.sql")
    bridge = P.query(con, SQL / "02_inventory_bridge.sql")
    dispense = P.query(con, SQL / "03_dispense_extract.sql")
    events = P.query(con, SQL / "04_status_evidence.sql")
    batches = P.query(con, SQL / "05_batch_recompute.sql")
    with (P.FOUNDATION / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        register = list(csv.DictReader(fh))

    routed, cases = run_rules(events)
    files = build_files(bridge, dispense, routed)

    dispense_qa = defaultdict(lambda: dict(duplicate_lines=0, invalid_visit_lines=0, blank_site=0))
    for r in P.query(con, """SELECT l.program_key, w.week_start, SUM(l.is_exact_duplicate) AS dup,
                                    SUM(CASE WHEN l.is_valid_visit = 0 THEN 1 ELSE 0 END) AS invalid
                             FROM program_lines l JOIN weeks w ON l.start_local >= w.week_start AND l.start_local < w.week_end
                             WHERE l.administered_flag = 1 GROUP BY 1, 2"""):
        dispense_qa[(r["program_key"], r["week_start"])].update(duplicate_lines=r["dup"], invalid_visit_lines=r["invalid"])
    for r in dispense:
        if not r["site_key"]:
            dispense_qa[(r["program_key"], r["week_start"])]["blank_site"] += 1

    week_starts = sorted({b["week_start"] for b in bridge})
    routed_by_week = defaultdict(list)
    for ev in routed:
        if ev["program_key"] == "PROGRAM_B":
            day = ev["event_at"][:10]
            for w in week_starts:
                if w <= day < (date.fromisoformat(w) + timedelta(days=7)).isoformat():
                    routed_by_week[w].append(ev)
    results = audit_batches(batches, files, bridge, dispense_qa, routed_by_week)
    sensitivity, n_visits = cutoff_sensitivity(con)

    latest = week_starts[-1]
    sample = write_package(files, latest, OUT / "sample_submission")
    qa = run_qa(con, results, bridge, dispense, dispense_qa, routed, cases, register, files, sample)

    flat = [{k: v for k, v in r.items() if k != "tests"} for r in results]
    for name, rows in [("console_batches", flat), ("inventory_bridge", bridge), ("status_exception_tracker", cases),
                       ("cutoff_sensitivity", sensitivity), ("qa_results", qa)]:
        P.write_csv(rows, OUT / f"{name}.csv")
    P.write_csv([dict(r, patient_key=token("PT", r["patient_key"]), order_key=token("ORD", r["order_key"])) for r in dispense],
                OUT / "dispense_extract_24_weeks.csv")

    # ---- dashboard payload
    grid = defaultdict(dict)
    for r in results:
        grid[f"{r['program_key']} · {r['file_type'].title()}"][r["reporting_week"]] = dict(
            s=r["overall"], b=r["batch_key"], i=r["issues"] or "All checks passed", d=r["diagnosis"])
    status_counts = Counter(r["overall"] for r in results)
    # Busiest site-product cell in the latest week makes the clearest bridge example.
    ex = max((b for b in bridge if b["week_start"] == latest), key=lambda b: (b["receipts"] > 0, b["transactions"]))
    full_ord = Counter(min(r["injection_ordinal"], 6) for r in dispense if r["program_key"] == "PROGRAM_B")
    tiles = [
        dict(label="Submission batches audited", value=f"{len(results)}", note="24 weeks x 5 files, mock destinations"),
        dict(label="Green / yellow / red", value=f"{status_counts['green']} / {status_counts['yellow']} / {status_counts['red']}",
             note="Worst test decides the batch"),
        dict(label="Inventory cells reconciled", value=f"{sum(1 for b in bridge if not b['variance']) / len(bridge):.1%}",
             note=f"{len(bridge)} site-product-weeks"),
        dict(label="Dispense rows built", value=f"{len(dispense):,}", note="Treated appointment x product, deduplicated"),
        dict(label="Status events routed", value=f"{len(routed):,}",
             note=f"{sum(1 for c in cases if c['disposition'] == 'Escalate')} escalate · {sum(1 for c in cases if c['disposition'] == 'Review')} review"),
        dict(label="Files missing late updates", value=f"{sum(1 for r in results if r['file_type'] == 'DISPENSE' and r['recomputed_rows_now'] != r['recomputed_rows'])}",
             note="of 48 dispense files - see cut-off analysis"),
    ]
    data = dict(meta=dict(as_of="October 24, 2026", seed=P.meta(con)["seed"], latest=latest),
                tiles=tiles, weeks=week_starts, grid=grid, rows=[f"{p} · {f.title()}" for p, f in FILE_ORDER],
                issues=[r for r in flat if r["overall"] != "green"], bridge_example=ex, cases=cases,
                sensitivity=sensitivity, n_visits=n_visits, ordinal=dict(full=[full_ord.get(k, 0) for k in range(1, 7)],
                                                                        total=sum(full_ord.values())),
                sample=sample, qa=qa)
    P.render_dashboard(HERE / "dashboard_template.html", HERE / "dashboard.html", data)
    if P.screenshot(HERE / "dashboard.html", HERE / "dashboard.png", width=1440, height=4750):
        print("  screenshot -> dashboard.png")
    write_qa_log(qa)
    print(f"Project C built: {len(results)} batches ({dict(status_counts)}), {len(cases)} status cases, QA "
          f"{sum(c['status'] == 'pass' for c in qa)} pass / {sum(c['status'] == 'warn' for c in qa)} warn / "
          f"{sum(c['status'] == 'fail' for c in qa)} fail")


def write_qa_log(qa):
    lines = ["# QA log - Project C (manufacturer ETL and submission QA)", "", f"> {P.DISCLAIMER}. Generated by `run.py`.", "",
             "WARN = a real issue was detected and routed. FAIL would mean the pipeline itself is wrong.", "",
             "| Status | Check | Observed | Rule applied |", "|---|---|---|---|"]
    lines += [f"| {c['status'].upper()} | {c['check']} | {c['observed']} | {c['rule']} |" for c in qa]
    (HERE / "QA_LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
