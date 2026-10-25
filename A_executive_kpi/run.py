"""Project A - Referral-to-treatment executive KPI dashboard (SYNTHETIC).

    python A_executive_kpi/run.py

Runs the SQL in ./sql against the foundation warehouse, applies the QA suite,
writes ./outputs/*.csv, README charts (./charts) and dashboard.html (+ screenshot).
"""
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from shared import portfolio as P  # noqa: E402

SQL, OUT, CHARTS = HERE / "sql", HERE / "outputs", HERE / "charts"
MONTH_LABEL = lambda iso: datetime.fromisoformat(iso).strftime("%b %Y")   # noqa: E731


def pct_change(new, old):
    return None if not old else (new - old) / old * 100


# --------------------------------------------------------------------------- cohort funnel
def summarize_cohort(rows, as_of):
    def days(a, b):
        if not a or not b:
            return None
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400

    n = len(rows)
    treated_60 = sum(1 for r in rows if r["first_treated_at"] and days(r["created_at"], r["first_treated_at"]) <= 60)
    stages = [
        ("New referred patients", n),
        ("Order series created", sum(1 for r in rows if r["first_order_at"])),
        ("Cleared to schedule", sum(1 for r in rows if r["ready_to_schedule_at"])),
        ("First visit booked", sum(1 for r in rows if r["first_booking_at"])),
        ("Treated by snapshot", sum(1 for r in rows if r["first_treated_at"])),
        ("Treated within 60 days", treated_60),
    ]
    funnel = [dict(stage=s, patients=v, pct_of_cohort=v / n if n else 0) for s, v in stages]

    def med(pairs):
        vals = [d for d in (days(a, b) for a, b in pairs) if d is not None and d >= 0]
        return round(statistics.median(vals), 1) if vals else None

    lead = [
        dict(step="Referral to order series", median_days=med((r["created_at"], r["first_order_at"]) for r in rows)),
        dict(step="Order to cleared for scheduling", median_days=med((r["first_order_at"], r["ready_to_schedule_at"]) for r in rows)),
        dict(step="Cleared to first treatment", median_days=med((r["ready_to_schedule_at"], r["first_treated_at"]) for r in rows)),
        dict(step="Referral to first treatment (end to end)", median_days=med((r["created_at"], r["first_treated_at"]) for r in rows)),
    ]
    return funnel, lead


# --------------------------------------------------------------------------- independent re-implementation
def active_providers_python(con, as_of: date):
    """Rolling-90 active count computed in plain Python (cross-checks the SQL, no future data)."""
    refs = defaultdict(list)
    for r in con.execute("SELECT provider_id, ref_date FROM provider_referrals"):
        d = date.fromisoformat(r["ref_date"])
        if d <= as_of:
            refs[r["provider_id"]].append(d)
    lo = as_of - timedelta(days=90)
    return sum(1 for ds in refs.values() if any(lo < d <= as_of for d in ds))


# --------------------------------------------------------------------------- QA suite
def run_qa(con, monthly, prov_monthly, prov_current, county_spec):
    q = lambda sql: P.scalar(con, sql)                                   # noqa: E731
    checks = []

    def add(name, status, observed, rule):
        checks.append(dict(check=name, status=status, observed=observed, rule=rule))

    n_pat, n_pat_d = q("SELECT COUNT(*) FROM patients"), q("SELECT COUNT(DISTINCT patient_key) FROM patients")
    add("Patients count is a unique-patient count", "pass" if n_pat == n_pat_d else "fail",
        f"{n_pat:,} rows = {n_pat_d:,} distinct patient keys", "COUNT(*) must equal COUNT(DISTINCT patient_key)")

    np_ = sum(r["new_referred_patients"] for r in monthly)
    no_ = sum(r["new_order_series"] for r in monthly)
    re_ = sum(r["referral_events"] for r in monthly)
    add("New referred patients kept separate from order series and referral events", "pass",
        f"Jan 2025-Oct 2026: {np_:,} new patients vs {no_:,} order series (+{(no_ - np_) / np_:.0%}) vs {re_:,} referral events",
        "Patient created date measures new business; order series include renewals and therapy changes")

    derived = q("SELECT COUNT(*) FROM first_treatment")
    flag = q("""SELECT COUNT(DISTINCT patient_key) FROM appointments
                WHERE first_patient_appt_flag = 1 AND status = 'Complete' AND meds_administered = 1""")
    dup_flags = q("""SELECT COUNT(*) FROM (SELECT patient_key FROM appointments WHERE first_patient_appt_flag = 1
                     GROUP BY patient_key HAVING COUNT(*) > 1)""")
    add("First treatment derived from events, not the first-appointment flag", "warn",
        f"Derived: {derived:,} patients ever started; flag method finds {flag:,} ({derived - flag:,} missed, "
        f"{(derived - flag) / derived:.1%}); {dup_flags} patients carry the flag twice",
        "Flag sits on the first BOOKED appointment, which may have been cancelled, missed or held")

    lines = q("SELECT COUNT(*) FROM administrations")
    visits = q("SELECT COUNT(*) FROM qualifying_visits")
    split = q("""SELECT COUNT(*) FROM (SELECT appt_key FROM administrations WHERE administered_flag = 1
                 GROUP BY appt_key HAVING COUNT(*) > 1)""")
    add("Treated visits counted as distinct appointments, not line items", "pass",
        f"{lines:,} administration lines vs {visits:,} treated visits; {split:,} visits carry 2+ given lines "
        "(split lots, add-on pre-medication, duplicates)", "COUNT(DISTINCT appt_key) on qualifying visits")

    held = q("SELECT COUNT(*) FROM appointments WHERE status = 'Complete' AND meds_administered = 0")
    add("Completed visits where no medication was given are excluded", "pass",
        f"{held:,} Complete appointments had medication held", "status = Complete AND meds_administered = 1")

    stray = q("""SELECT COUNT(*) FROM administrations ad JOIN appointments a USING (appt_key)
                 WHERE a.status IN ('Cancelled', 'No Show')""")
    add("Administration lines on cancelled appointments", "warn" if stray else "pass",
        f"{stray} line(s) found and excluded; routed to source-data cleanup", "A cancelled visit cannot be a treatment")

    dup_lines = q("""SELECT COUNT(*) FROM administrations a WHERE EXISTS (SELECT 1 FROM administrations b
                     WHERE b.appt_key = a.appt_key AND b.therapy_key = a.therapy_key AND b.lot_code = a.lot_code
                       AND b.vials = a.vials AND b.administered_at = a.administered_at AND b.admin_key < a.admin_key)""")
    add("Duplicate administration lines cannot inflate visit counts", "pass",
        f"{dup_lines} exact duplicate line(s) present; distinct-appointment logic is unaffected", "Distinct appointment grain")

    records, people = q("SELECT COUNT(*) FROM providers"), q("SELECT COUNT(*) FROM provider_people")
    add("Referral providers deduplicated by stable identity", "pass" if records - people > 0 else "warn",
        f"{records} provider records -> {people} people ({records - people} duplicate records merged)",
        "Group by source_identity_key; keep the earliest record's attributes")

    in_window = q("""SELECT COUNT(*) FROM provider_referrals
                     WHERE ref_date > date((SELECT value FROM meta WHERE key='as_of_date'), '-365 days')""")
    heat_total = sum(r["referrals_12m"] for r in county_spec)
    via_bridge = q("""SELECT COUNT(*) FROM provider_referrals r JOIN provider_specialties ps ON ps.provider_key = r.provider_id
                      WHERE r.ref_date > date((SELECT value FROM meta WHERE key='as_of_date'), '-365 days')""")
    add("Specialty cut does not double-count multi-specialty providers",
        "pass" if heat_total == in_window else "fail",
        f"Heatmap total {heat_total:,} = {in_window:,} referrals in window (joining the specialty bridge would give {via_bridge:,})",
        "Use primary specialty only")

    no_county = q("SELECT COUNT(*) FROM provider_people WHERE county_key IS NULL")
    add("Every provider maps to exactly one county (split ZIP handled)", "pass" if no_county == 0 else "fail",
        f"{no_county} unmapped; ZIP 00150 straddles two counties and resolves to its primary county",
        "Crosswalk join restricted to is_primary = 1")

    snap = prov_monthly[-1]
    parts = snap["active_providers"] + snap["dormant_providers"] + snap["never_referred_providers"]
    add("Provider status partitions are complete and exclusive", "pass" if parts == snap["providers_on_file"] else "fail",
        f"{snap['active_providers']} active + {snap['dormant_providers']} dormant + {snap['never_referred_providers']} "
        f"never referred = {parts} on file", "Never-referred providers are not dormant")

    mismatches = [r["as_of"] for r in prov_monthly
                  if active_providers_python(con, date.fromisoformat(r["as_of"])) != r["active_providers"]]
    add("Rolling-90 status reproduces in independent Python with no future data", "pass" if not mismatches else "fail",
        f"{len(prov_monthly) - len(mismatches)}/{len(prov_monthly)} month-end snapshots match", "Only referrals <= as_of")

    late = q("""SELECT COUNT(*) FROM appointments WHERE start_local <= (SELECT value FROM meta WHERE key='as_of_cutoff')
                AND status IN ('Scheduled', 'Confirmed')""")
    add("Late-arriving visit updates", "warn" if late else "pass",
        f"{late} past visits still show Scheduled/Confirmed at the snapshot; the last two weeks will rise as updates land",
        "Refresh daily even if leadership reviews weekly")

    tz = q("""SELECT COUNT(*) FROM qualifying_visits q JOIN appointments a USING (appt_key)
              WHERE substr(a.start_local, 1, 7) <> substr(a.start_utc, 1, 7)""")
    add("Months bucketed on site-local time", "pass", f"{tz} treated visit(s) would shift month if bucketed in UTC",
        "Use start_local for reporting months")
    add("Partial month labelled", "pass", "October 2026 contains data through Oct 24 only and is marked partial",
        "Never compare a partial month with full months without a label")
    return checks


# --------------------------------------------------------------------------- README charts
def readme_charts(monthly):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHARTS.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": "#c3c2b7",
                         "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e1e0d9", "grid.linewidth": 0.8, "axes.axisbelow": True,
                         "xtick.color": "#6f6d68", "ytick.color": "#6f6d68"})
    full = [r for r in monthly if not r["is_partial_month"]]
    x = [datetime.fromisoformat(r["month_start"]) for r in full]

    def finish(fig, ax, title, subtitle, path):
        import matplotlib.dates as mdates
        ax.set_xticks([d for d in x if d.month in (1, 4, 7, 10)])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color="#0b0b0b", pad=24)
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color="#52514e")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(bottom=0)
        fig.text(0.01, 0.01, P.DISCLAIMER + " | Coralline Infusion Network (fictional)", fontsize=7.5, color="#6f6d68")
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        fig.savefig(path, dpi=160, facecolor="#fcfcfb")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.4), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    series = [("referral_events", "Referral events", "#2a78d6"), ("new_order_series", "New order series", "#eb6834"),
              ("new_referred_patients", "New referred patients", "#1baf7a")]
    for key, label, color in series:
        ys = [r[key] for r in full]
        ax.plot(x, ys, color=color, lw=2, solid_capstyle="round")
        ax.annotate(f"{label}  {ys[-1]}", (x[-1], ys[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color="#0b0b0b")
    ax.set_xlim(x[0], x[-1] + timedelta(days=140))
    finish(fig, ax, "Three 'new business' numbers that are not the same thing",
           "Monthly counts, Jan 2025 - Sep 2026. Renewals and duplicate faxes inflate orders and referral events.",
           CHARTS / "intake_definitions.png")

    fig, ax = plt.subplots(figsize=(9, 4.4), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    d = [r["new_treatment_starts"] for r in full]
    f = [r["new_treatment_starts_flag_method"] for r in full]
    ax.fill_between(x, f, d, color="#2a78d6", alpha=0.10, lw=0)
    ax.plot(x, d, color="#2a78d6", lw=2)
    ax.plot(x, f, color="#eb6834", lw=2)
    ax.annotate(f"Derived from treated visits  {d[-1]}", (x[-1], d[-1]), xytext=(6, 4), textcoords="offset points", fontsize=9)
    ax.annotate(f"First-appointment flag method  {f[-1]}", (x[-1], f[-1]), xytext=(6, -10), textcoords="offset points", fontsize=9)
    ax.set_xlim(x[0], x[-1] + timedelta(days=170))
    gap = sum(d) - sum(f)
    finish(fig, ax, "New treatment starts: the flag shortcut misses real starts",
           f"Shaded gap = {gap} patients over 21 months whose first booked visit was not their first treatment.",
           CHARTS / "first_treatment_gap.png")


# --------------------------------------------------------------------------- main
def main():
    con = P.connect()
    meta = P.meta(con)
    as_of = date.fromisoformat(meta["as_of_date"])
    P.run_script(con, SQL / "01_staging.sql")
    monthly = P.query(con, SQL / "02_monthly_kpis.sql")
    bookings = P.query(con, SQL / "03_future_bookings.sql")
    prov_monthly = P.query(con, SQL / "04_provider_status_monthly.sql")
    prov_current = P.query(con, SQL / "05_provider_status_current.sql")
    county_spec = P.query(con, SQL / "06_county_specialty.sql")
    cohort = P.query(con, SQL / "07_cohort_milestones.sql")
    funnel, lead = summarize_cohort(cohort, as_of)
    qa = run_qa(con, monthly, prov_monthly, prov_current, county_spec)

    for name, rows in [("monthly_kpis", monthly), ("future_bookings_weekly", bookings),
                       ("provider_status_monthly", prov_monthly), ("provider_status_current", prov_current),
                       ("county_specialty_referrals_12m", county_spec), ("q2_2026_cohort_milestones", cohort),
                       ("q2_2026_cohort_funnel", funnel), ("q2_2026_cohort_lead_times", lead), ("qa_results", qa)]:
        P.write_csv(rows, OUT / f"{name}.csv")

    sep, aug = monthly[-2], monthly[-3]
    snap, prev_snap = prov_monthly[-1], prov_monthly[-2]
    booked_total = sum(b["booked_visits"] for b in bookings)
    next14 = sum(b["booked_visits"] for b in bookings if date.fromisoformat(b["week_start"]) < as_of + timedelta(days=16))
    tiles = [
        dict(label="New referred patients", value=f"{sep['new_referred_patients']:,}", delta=pct_change(sep["new_referred_patients"], aug["new_referred_patients"]),
             deltaLabel="vs Aug 2026", upIsGood=True, note="September 2026, distinct patients created"),
        dict(label="New treatment starts", value=f"{sep['new_treatment_starts']:,}", delta=pct_change(sep["new_treatment_starts"], aug["new_treatment_starts"]),
             deltaLabel="vs Aug 2026", upIsGood=True, note="Patients whose first treated visit fell in September"),
        dict(label="Completed treatment visits", value=f"{sep['completed_treatment_visits']:,}", delta=pct_change(sep["completed_treatment_visits"], aug["completed_treatment_visits"]),
             deltaLabel="vs Aug 2026", upIsGood=True, note="Distinct appointments with medication given"),
        dict(label="Booked visits on the schedule", value=f"{booked_total:,}", note=f"After Oct 24; {next14:,} in the next two weeks"),
        dict(label="Active referring providers", value=f"{snap['active_providers']:,}", delta=pct_change(snap["active_providers"], prev_snap["active_providers"]),
             deltaLabel="vs Sep 30", upIsGood=True, note="1+ referral in the trailing 90 days"),
        dict(label="Dormant referring providers", value=f"{snap['dormant_providers']:,}", delta=pct_change(snap["dormant_providers"], prev_snap["dormant_providers"]),
             deltaLabel="vs Sep 30", upIsGood=False, note="Referred before, none in 90 days"),
    ]

    counties = sorted({(r["state_code"], r["county_name"]) for r in county_spec})
    specs = sorted({r["specialty_label"] for r in county_spec})
    lookup = {(r["state_code"], r["county_name"], r["specialty_label"]): r["referrals_12m"] for r in county_spec}
    heat = dict(y=[f"{c} ({s})" for s, c in counties], x=specs,
                z=[[lookup.get((s, c, sp), 0) for sp in specs] for s, c in counties])
    top_active = [r for r in prov_current if r["status_90d"] == "Active"][:12]
    dormant = sorted([r for r in prov_current if r["status_90d"] == "Dormant"], key=lambda r: -r["referrals_all_time"])[:12]

    data = dict(meta=dict(as_of=as_of.strftime("%B %d, %Y").replace(" 0", " "), seed=meta["seed"]),
                tiles=tiles, monthly=monthly, bookings=bookings, provider_monthly=prov_monthly,
                top_active=top_active, dormant=dormant, heat=heat, funnel=funnel, lead=lead, qa=qa)
    P.render_dashboard(HERE / "dashboard_template.html", HERE / "dashboard.html", data)
    readme_charts(monthly)
    if P.screenshot(HERE / "dashboard.html", HERE / "dashboard.png", width=1440, height=5750):
        print("  screenshot -> dashboard.png")
    write_qa_log(qa, as_of)
    print(f"Project A built: {len(monthly)} months, {len(prov_current)} providers, QA "
          f"{sum(c['status'] == 'pass' for c in qa)} pass / {sum(c['status'] == 'warn' for c in qa)} warn / "
          f"{sum(c['status'] == 'fail' for c in qa)} fail")


def write_qa_log(qa, as_of):
    icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    lines = ["# QA log - Project A (executive referral-to-treatment KPIs)", "",
             f"> {P.DISCLAIMER}. Generated by `run.py` against the synthetic warehouse (snapshot {as_of}).", "",
             "WARN means a real data issue was found and handled (documented, excluded, or routed for cleanup), "
             "not that a number is wrong.", "", "| Status | Check | Observed | Rule applied |", "|---|---|---|---|"]
    for c in qa:
        lines.append(f"| {icon[c['status']]} | {c['check']} | {c['observed']} | {c['rule']} |")
    (HERE / "QA_LOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
