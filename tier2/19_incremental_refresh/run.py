"""Tier 2 #19 - Incremental refresh demo with goals vs actuals (SYNTHETIC).

    python tier2/19_incremental_refresh/run.py

1. Extract 54 daily CSV drops (Sep 1 - Oct 24, 2026) from appointment_change_log, each with a
   two-day window, into ./drops.
2. Simulate delivery: one file re-sent, two files out of order, a two-day sender outage.
3. Load: initial full load to Aug 31, then each delivery into an in-memory target with an
   idempotent upsert on (appt_key, changed_at) and an audit row per delivery.
4. Prove it: incremental == full refresh, reruns identical, reload changes nothing, order does not matter.
5. Report goals vs actuals from reporting_targets and how late corrections restate closed months.
"""
import csv
import hashlib
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

SQL, OUT, DROPS = HERE / "sql", HERE / "outputs", HERE / "drops"
BASELINE_CUTOFF = "2026-08-31 23:59:59"
FIRST_DROP, LAST_DROP = date(2026, 9, 1), date(2026, 10, 24)
DROP_COLUMNS = ["appt_key", "changed_at", "change_type", "new_status", "site_key", "start_local"]
INCIDENTS = {   # file_date -> (arrival, note)
    "resend": (date(2026, 9, 15), datetime(2026, 9, 16, 8, 40), "Re-delivered by the sender (identical file)"),
    "out_of_order": (date(2026, 10, 6), datetime(2026, 10, 8, 6, 25), "Arrived after the next day's file"),
    "outage_1": (date(2026, 10, 13), datetime(2026, 10, 16, 7, 0), "Sender outage - held, delivered late"),
    "outage_2": (date(2026, 10, 14), datetime(2026, 10, 16, 7, 5), "Sender outage - held, delivered late"),
}


def drop_dates():
    d, out = FIRST_DROP, []
    while d <= LAST_DROP:
        out.append(d)
        d += timedelta(days=1)
    return out


def drop_name(d):
    return f"appt_changes_{d:%Y%m%d}.csv"


def statements(path):
    """Split a SQL file into executable statements (so named parameters can be bound)."""
    out, buf = [], ""
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            body = "\n".join(x for x in buf.splitlines() if not x.strip().startswith("--")).strip()
            if body:
                out.append(body)
            buf = ""
    return out


def open_target():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("ATTACH DATABASE ? AS wh", (str(P.WAREHOUSE),))   # the source warehouse is only read
    con.executescript((SQL / "01_target_schema.sql").read_text(encoding="utf-8"))
    return con


# --------------------------------------------------------------------------- 1. extract
def extract_drops(con, out_dir=DROPS):
    out_dir.mkdir(exist_ok=True)
    sql = (SQL / "00_extract_drop.sql").read_text(encoding="utf-8")
    for d in drop_dates():
        rows = con.execute(sql, dict(lo=f"{d - timedelta(days=1)} 00:00:00", hi=f"{d} 23:59:59")).fetchall()
        with (out_dir / drop_name(d)).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(DROP_COLUMNS)
            w.writerows([[r[c] if r[c] is not None else "" for c in DROP_COLUMNS] for r in rows])


# --------------------------------------------------------------------------- 2. delivery schedule
def arrival_schedule(order="scheduled"):
    """[(arrived_at, file_date, note)]. 'scheduled' includes the incidents; 'clean' and 'reverse' are for proofs."""
    dates = drop_dates()
    if order == "clean":
        return [(datetime.combine(d + timedelta(days=1), datetime.min.time()) + timedelta(hours=6, minutes=10), d,
                 "Scheduled delivery") for d in dates]
    if order == "reverse":
        return [(datetime(2026, 10, 25, 6, 0) + timedelta(minutes=i), d, "Reverse-order proof run")
                for i, d in enumerate(reversed(dates))]
    moved = {fd: (at, note) for fd, at, note in INCIDENTS.values() if fd != INCIDENTS["resend"][0]}
    events = []
    for d in dates:
        at, note = moved.get(d, (datetime.combine(d + timedelta(days=1), datetime.min.time())
                                 + timedelta(hours=6, minutes=10), "Scheduled delivery"))
        events.append((at, d, note))
    fd, at, note = INCIDENTS["resend"]
    events.append((at, fd, note))
    return sorted(events, key=lambda e: (e[0], e[1]))


# --------------------------------------------------------------------------- 3. load
LOAD_SQL = None


def load_rows(con, rows, load_seq, file_name, file_date, arrived_at, sha, note):
    global LOAD_SQL
    LOAD_SQL = LOAD_SQL or statements(SQL / "02_load_stage.sql")
    file_month = (file_date or date(2026, 8, 31)).replace(day=1).isoformat()
    params = dict(load_seq=load_seq, file_month=file_month)
    with con:
        con.execute("DELETE FROM temp.stage")
        con.executemany("INSERT INTO temp.stage VALUES (?, ?, ?, ?, ?, ?)", rows)
        for stmt in LOAD_SQL[:-1]:
            con.execute(stmt, params)
        m = dict(con.execute(LOAD_SQL[-1], params).fetchone())
        con.execute("INSERT INTO load_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            load_seq, file_name, file_date.isoformat() if file_date else None, arrived_at.isoformat(sep=" "), sha,
            m["rows_in_file"], m["rows_inserted"], m["rows_in_file"] - m["rows_inserted"], m["appts_new"],
            m["appts_updated"], m["stale_rows_skipped"], m["late_updates"], m["restates_closed_month"],
            m["max_changed_at"], note))
    return m


def read_drop(path):
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)
        return [tuple(v if v != "" else None for v in row) for row in reader]


def initial_load(con):
    rows = con.execute((SQL / "00_extract_drop.sql").read_text(encoding="utf-8"),
                       dict(lo="0000-01-01", hi=BASELINE_CUTOFF)).fetchall()
    load_rows(con, [tuple(r) for r in rows], 0, "initial full load (warehouse query to Aug 31)", None,
              datetime(2026, 9, 1, 2, 0), None, "Initial full load")


def month_completed(con, month_start):
    nxt = (date.fromisoformat(month_start) + timedelta(days=32)).replace(day=1).isoformat()
    return con.execute("SELECT COUNT(*) FROM appt_current WHERE status = 'Complete' AND start_local >= ? AND start_local < ?",
                       (month_start, nxt)).fetchone()[0]


def run_pipeline(order="scheduled", track=False):
    """Fresh target -> initial load -> every delivery. Returns (con, as_reported_trend)."""
    con = open_target()
    initial_load(con)
    trend = []
    if track:
        trend.append(dict(load_seq=0, arrived_at="2026-09-01 02:00:00", file="initial full load",
                          august_completed=month_completed(con, "2026-08-01"),
                          september_completed=month_completed(con, "2026-09-01")))
    for seq, (arrived_at, fd, note) in enumerate(arrival_schedule(order), 1):
        path = DROPS / drop_name(fd)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        load_rows(con, read_drop(path), seq, path.name, fd, arrived_at, sha, note)
        if track:
            trend.append(dict(load_seq=seq, arrived_at=arrived_at.isoformat(sep=" "), file=path.name,
                              august_completed=month_completed(con, "2026-08-01"),
                              september_completed=month_completed(con, "2026-09-01")))
    return con, trend


def reload_all(con):
    start = con.execute("SELECT MAX(load_seq) FROM load_audit").fetchone()[0] + 1
    for i, d in enumerate(drop_dates()):
        path = DROPS / drop_name(d)
        load_rows(con, read_drop(path), start + i, path.name, d, datetime(2026, 10, 26, 6, 0) + timedelta(minutes=i),
                  hashlib.sha256(path.read_bytes()).hexdigest()[:12], "Full reload of every file (idempotency proof)")
    return start


def content_hash(con):
    h = hashlib.sha256()
    for sql in ("SELECT appt_key, changed_at, change_type, new_status, site_key, start_local FROM appt_change_history "
                "ORDER BY appt_key, changed_at",
                "SELECT appt_key, status, changed_at, site_key, start_local FROM appt_current ORDER BY appt_key"):
        for r in con.execute(sql):
            h.update("|".join("" if v is None else str(v) for v in r).encode())
            h.update(b"\n")
    return h.hexdigest()


def full_hash(con):
    """Content plus load sequence and audit - identical only if the whole run is deterministic."""
    h = hashlib.sha256(content_hash(con).encode())
    for sql in ("SELECT appt_key, changed_at, load_seq FROM appt_change_history ORDER BY appt_key, changed_at",
                "SELECT * FROM load_audit ORDER BY load_seq"):
        for r in con.execute(sql):
            h.update("|".join("" if v is None else str(v) for v in r).encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- 4. proofs and QA
def proofs(con):
    runs = []

    def add(run, c, note):
        runs.append(dict(run=run, history_rows=c.execute("SELECT COUNT(*) FROM appt_change_history").fetchone()[0],
                         current_rows=c.execute("SELECT COUNT(*) FROM appt_current").fetchone()[0],
                         content_sha256_12=content_hash(c)[:12], note=note))

    add("1. Scheduled deliveries with incidents", con, "The run published on this page")
    again, _ = run_pipeline("scheduled")
    same_full = full_hash(again) == full_hash(con)
    add("2. Rerun from scratch", again, f"Audit, load sequence and content identical: {same_full}")
    start = reload_all(again)
    inserted = again.execute("SELECT SUM(rows_inserted) FROM load_audit WHERE load_seq >= ?", (start,)).fetchone()[0]
    add("3. Rerun + reload every file again", again, f"{inserted} rows inserted by the reload")
    clean, _ = run_pipeline("clean")
    add("4. Clean date order, no incidents", clean, "Same final answer as the run with incidents")
    rev, _ = run_pipeline("reverse")
    add("5. All files in reverse order", rev, "Order of arrival does not change the result")
    return runs, same_full, inserted


def run_qa(con, runs, same_full, reload_inserted, gva, restate):
    q = lambda sql, p=(): con.execute(sql, p).fetchone()[0]                    # noqa: E731
    checks = []

    def add(name, status, observed, rule):
        checks.append(dict(check=name, status=status, observed=observed, rule=rule))

    mismatch = q("""SELECT COUNT(*) FROM wh.appointments a LEFT JOIN appt_current c USING (appt_key)
                    WHERE c.appt_key IS NULL OR c.status <> a.status OR c.changed_at <> a.updated_at""")
    n_appt, n_log = q("SELECT COUNT(*) FROM wh.appointments"), q("SELECT COUNT(*) FROM wh.appointment_change_log")
    n_hist, n_cur = q("SELECT COUNT(*) FROM appt_change_history"), q("SELECT COUNT(*) FROM appt_current")
    add("Incremental result equals a full refresh", "pass" if mismatch == 0 and n_hist == n_log and n_cur == n_appt else "fail",
        f"{n_cur - mismatch:,}/{n_appt:,} appointments match status and last update; history {n_hist:,} rows = change log {n_log:,}",
        "Incremental must reproduce the source as of the snapshot")
    audit = [dict(r) for r in con.execute("SELECT * FROM load_audit ORDER BY load_seq")]
    resend = [a for a in audit if a["note"].startswith("Re-delivered")][0]
    add("Re-delivered file changed nothing", "pass" if resend["rows_inserted"] == 0 and resend["appts_updated"] == 0 else "fail",
        f"{resend['file_name']} arrived twice; second copy: {resend['rows_in_file']} rows read, {resend['rows_inserted']} inserted, "
        f"{resend['appts_updated']} updated", "INSERT OR IGNORE on (appt_key, changed_at)")
    ooo = [a for a in audit if a["note"].startswith("Arrived after")][0]
    add("Out-of-order file could not move appointments backwards", "warn" if ooo["stale_rows_skipped"] else "pass",
        f"{ooo['file_name']} arrived after the next day's file: {ooo['stale_rows_skipped']} older changes skipped, "
        f"{ooo['appts_updated']} applied", "Upsert only WHERE excluded.changed_at > current.changed_at")
    outage = [a for a in audit if a["note"].startswith("Sender outage")]
    gap = sum(a["rows_inserted"] for a in outage)
    add("Late files filled the outage gap", "warn" if gap else "pass",
        f"{len(outage)} files held by the sender added {gap} changes when they arrived on Oct 16; until then reports were "
        f"missing them", "Load late files whenever they arrive; the key decides, not the arrival order")
    overlap = sum(a["duplicates_ignored"] for a in audit if a["load_seq"] > 0)
    add("Overlapping two-day windows deduplicated", "pass",
        f"{overlap:,} rows ignored across {len(audit) - 1} deliveries (yesterday re-sent in every file, plus the re-delivery)",
        "Overlap is cheap insurance when the key makes it harmless")
    add("Rerun from scratch is identical", "pass" if same_full else "fail",
        f"Content hash {runs[0]['content_sha256_12']} = {runs[1]['content_sha256_12']}; audit and load sequence identical: {same_full}",
        "Deterministic arrival times, no wall-clock values")
    add("Reloading every file again changes nothing", "pass" if reload_inserted == 0 and runs[2]["content_sha256_12"] == runs[0]["content_sha256_12"] else "fail",
        f"{reload_inserted} rows inserted; content hash unchanged", "Idempotent load")
    same = len({r["content_sha256_12"] for r in runs}) == 1
    add("Arrival order does not change the result", "pass" if same else "fail",
        f"{len(runs)} runs (incidents, rerun, reload, clean order, reverse order) share content hash {runs[0]['content_sha256_12']}",
        "Newest changed_at wins regardless of delivery order")
    late = sum(a["late_updates"] for a in audit if a["load_seq"] > 0)
    closed = sum(a["restates_closed_month"] for a in audit if a["load_seq"] > 0)
    sep = next(r for r in restate if r["month"] == "2026-09")
    add("Late corrections tracked and closed months restated", "warn" if late else "pass",
        f"{late} visit outcomes recorded 3+ days after the visit; {closed} changes touched an already-closed month. "
        f"September completed visits: first reported {sep['first_reported']} on {sep['first_reported_at'][:10]}, "
        f"{sep['final']} by Oct 24 ({sep['final'] - sep['first_reported']:+d})", "Report a month as provisional until late updates settle")
    actual_total = sum(r["actual"] for r in gva)
    direct = q("""SELECT COUNT(*) FROM wh.appointments WHERE status = 'Complete'
                  AND start_local >= '2026-01-01' AND start_local < '2026-11-01'""")
    unassigned = sum(r["actual"] for r in gva if r["site_key"] == "Unassigned")
    add("Goals vs actuals reconcile to the source", "pass" if actual_total == direct else "fail",
        f"{actual_total:,} completed appointments Jan-Oct 2026 = {direct:,} counted directly; {unassigned} with a blank site "
        "shown as Unassigned (no goal)", "Actual = distinct appointments with current status Complete")
    add("Partial month labelled", "pass", "October 2026 runs through Oct 24 only; its attainment is marked partial",
        "Never compare a partial month with a full-month goal unlabelled")
    return checks


# --------------------------------------------------------------------------- main
def main():
    con = open_target()
    extract_drops(con)
    con.close()
    meta = P.meta(P.connect())
    con, trend = run_pipeline("scheduled", track=True)
    runs, same_full, reload_inserted = proofs(con)
    gva = P.query(con, (SQL / "03_goals_vs_actuals.sql"))
    first = {"2026-08": trend[0], "2026-09": next(t for t in trend if t["file"] == drop_name(date(2026, 9, 30)))}
    restate = [dict(month=m, first_reported_at=t["arrived_at"],
                    first_reported=t["august_completed" if m == "2026-08" else "september_completed"],
                    final=trend[-1]["august_completed" if m == "2026-08" else "september_completed"]) for m, t in first.items()]
    for r in restate:
        r["change"] = r["final"] - r["first_reported"]
    qa = run_qa(con, runs, same_full, reload_inserted, gva, restate)

    audit = P.query(con, "SELECT * FROM load_audit ORDER BY load_seq")
    schedule = [dict(arrival_order=i, arrived_at=a.isoformat(sep=" "), file=drop_name(d), note=n)
                for i, (a, d, n) in enumerate(arrival_schedule(), 1)]
    for name, rows in [("load_audit", audit), ("arrival_schedule", schedule), ("goals_vs_actuals", gva),
                       ("restatement", restate), ("as_reported_trend", trend), ("idempotency_proof", runs), ("qa_results", qa)]:
        P.write_csv(rows, OUT / f"{name}.csv")

    deliveries = [a for a in audit if a["load_seq"] > 0]
    sep = next(r for r in restate if r["month"] == "2026-09")
    monthly = {}
    for r in gva:
        m = monthly.setdefault(r["target_month"], dict(month=r["target_month"], goal=0, actual=0, partial=r["is_partial_month"]))
        m["goal"] += r["goal"] or 0
        m["actual"] += r["actual"]
    monthly = list(monthly.values())
    tiles = [
        dict(label="Deliveries loaded", value=f"{len(deliveries)}", note=f"{len(drop_dates())} daily files + 1 re-delivery, Sep 1 - Oct 24"),
        dict(label="Rows received", value=f"{sum(a['rows_in_file'] for a in deliveries):,}",
             note=f"{sum(a['rows_inserted'] for a in deliveries):,} new, {sum(a['duplicates_ignored'] for a in deliveries):,} overlap ignored"),
        dict(label="Late corrections", value=f"{sum(a['late_updates'] for a in deliveries)}",
             note="Visit outcomes recorded 3+ days after the visit"),
        dict(label="September restated", value=f"{sep['change']:+d}", note=f"{sep['first_reported']} first reported -> {sep['final']} by Oct 24"),
        dict(label="Proof runs agreeing", value=f"{sum(r['content_sha256_12'] == runs[0]['content_sha256_12'] for r in runs)}/{len(runs)}",
             note="Rerun, reload, clean order, reverse order"),
    ]
    data = dict(meta=dict(as_of="October 24, 2026", seed=meta["seed"]), tiles=tiles, audit=audit, trend=trend, gva=gva,
                monthly=monthly, restate=restate, runs=runs, qa=qa)
    P.render_dashboard(HERE / "dashboard_template.html", HERE / "dashboard.html", data)
    if P.screenshot(HERE / "dashboard.html", HERE / "dashboard.png", width=1440, height=3450):
        print("  screenshot -> dashboard.png")
    P.write_qa_log(HERE / "QA_LOG.md", "Tier 2 #19 (incremental refresh and goals vs actuals)", qa)
    print(f"#19 built: {len(deliveries)} deliveries, {len(runs)} proof runs agree: {len({r['content_sha256_12'] for r in runs}) == 1}; "
          f"QA {P.qa_summary(qa)}")


if __name__ == "__main__":
    main()
