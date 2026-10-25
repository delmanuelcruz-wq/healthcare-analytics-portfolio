"""Tier 2 #09 - Pulmonology/immunology referral-source analysis (SYNTHETIC).

    python tier2/09_specialty_referral_sources/run.py

Leaderboard of referral sources, 12-month trend and provider-county distribution for
providers who practice pulmonology or immunology/allergy. Each provider person is counted
once, duplicate faxes are excluded, and the location definition is printed on the page.
"""
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

SQL, OUT = HERE / "sql", HERE / "outputs"
WINDOW = ("2025-10-01", "2026-10-01")   # half-open, 12 full months
SCOPE_CODES = {"PUL", "IMM"}


def load(con):
    P.run_script(con, SQL / "01_staging.sql")
    return dict(leaderboard=P.query(con, SQL / "02_leaderboard.sql"), trend=P.query(con, SQL / "03_monthly_trend.sql"),
                county=P.query(con, SQL / "04_county_distribution.sql"), audit=P.query(con, SQL / "05_double_count_audit.sql"),
                people=P.query(con, "SELECT * FROM scope_people ORDER BY provider_id"))


# --------------------------------------------------------------------------- independent re-implementation
def recompute_python(con):
    """Referrals per provider person in plain Python, written from the business rules (cross-checks the SQL)."""
    records = list(con.execute("SELECT provider_key, source_identity_key FROM providers"))
    person_of_identity = {}
    for r in sorted(records, key=lambda r: r["provider_key"]):
        person_of_identity.setdefault(r["source_identity_key"], r["provider_key"])
    person = {r["provider_key"]: person_of_identity[r["source_identity_key"]] for r in records}
    in_scope = {person[r["provider_key"]] for r in con.execute("SELECT provider_key, specialty_code FROM provider_specialties")
                if r["specialty_code"] in SCOPE_CODES}
    counts = defaultdict(int)
    for r in con.execute("SELECT provider_key, referral_at, referral_type FROM referrals"):
        p = person[r["provider_key"]]
        if p in in_scope and WINDOW[0] <= r["referral_at"] < WINDOW[1] and r["referral_type"] != "Duplicate":
            counts[p] += 1
    return dict(counts), in_scope


# --------------------------------------------------------------------------- QA suite
def run_qa(con, d):
    q = lambda sql: P.scalar(con, sql)                                        # noqa: E731
    checks = []

    def add(name, status, observed, rule):
        checks.append(dict(check=name, status=status, observed=observed, rule=rule))

    total = q("SELECT COUNT(*) FROM scope_referrals")
    board = sum(r["referrals_12m"] for r in d["leaderboard"])
    audit = {r["method"]: r for r in d["audit"]}
    shortcut = next(r for m, r in audit.items() if m.startswith("Specialty-bridge join, duplicate"))
    both = q("""SELECT COUNT(*) FROM scope_people sp WHERE (SELECT COUNT(DISTINCT ps.specialty_code)
                FROM provider_identity pi JOIN provider_specialties ps ON ps.provider_key = pi.provider_key
                WHERE pi.provider_id = sp.provider_id AND ps.specialty_code IN ('PUL', 'IMM')) = 2""")
    secondary = sum(1 for p in d["people"] if p["specialty_group"].startswith("PUL/IMM"))
    add("Multi-specialty providers counted once", "pass" if board == total else "fail",
        f"Leaderboard total {board:,} = {total:,} distinct referral events. {both} provider(s) carry both specialties and "
        f"{secondary} carry PUL/IMM only as a secondary specialty; the specialty-bridge join would report {shortcut['referrals']:,}",
        "One row per provider person, one specialty group each (the primary specialty)")
    merged = [p for p in d["people"] if p["record_count"] > 1]
    on_dup = q("""SELECT COUNT(*) FROM scope_referrals r JOIN referrals x USING (referral_key)
                  WHERE x.provider_key <> r.provider_id""")
    add("Duplicate provider records merged", "warn" if merged else "pass",
        f"{len(merged)} in-scope provider(s) have two records ({', '.join(p['provider_id'] for p in merged)}); "
        f"{on_dup} referrals logged on the duplicate record roll up to the person", "Group by source_identity_key")
    dup_fax = q(f"""SELECT COUNT(*) FROM referrals r JOIN provider_identity pi ON pi.provider_key = r.provider_key
                    JOIN scope_people sp ON sp.provider_id = pi.provider_id
                    WHERE r.referral_at >= '{WINDOW[0]}' AND r.referral_at < '{WINDOW[1]}' AND r.referral_type = 'Duplicate'""")
    add("Duplicate faxes excluded", "warn" if dup_fax else "pass",
        f"{dup_fax} duplicate-fax referral events from in-scope providers removed", "referral_type <> 'Duplicate'")
    unmapped = sum(1 for p in d["people"] if p["county_key"] is None)
    add("Every in-scope provider maps to exactly one county", "pass" if unmapped == 0 else "fail",
        f"{unmapped} unmapped of {len(d['people'])}; split ZIP 00150 resolves to its primary county",
        "Crosswalk join restricted to is_primary = 1")
    trend_total, county_total = sum(r["referrals"] for r in d["trend"]), sum(r["referrals_12m"] for r in d["county"])
    add("Trend and county views sum to the leaderboard", "pass" if trend_total == county_total == board else "fail",
        f"trend {trend_total:,} = county {county_total:,} = leaderboard {board:,}", "Every view reads the same scoped rows")
    groups = defaultdict(int)
    for r in d["trend"]:
        groups[r["specialty_group"]] += 1
    add("Trend is zero-filled for 12 months per group", "pass" if set(groups.values()) == {12} else "fail",
        ", ".join(f"{g}: {n} months" for g, n in sorted(groups.items())), "A quiet month shows as 0, not as a gap")
    partial = q("""SELECT COUNT(*) FROM referrals r JOIN provider_identity pi ON pi.provider_key = r.provider_key
                   JOIN scope_people sp ON sp.provider_id = pi.provider_id
                   WHERE r.referral_at >= '2026-10-01' AND r.referral_type <> 'Duplicate'""")
    add("Window is 12 full months", "pass",
        f"Oct 1, 2025 - Sep 30, 2026; {partial} referrals from Oct 1-24, 2026 are excluded as a partial month",
        "Half-open window [2025-10-01, 2026-10-01)")
    other = sum(r["from_patients_in_other_counties"] for r in d["county"])
    add("Location definition is explicit", "pass",
        f"{other:,} of {county_total:,} referrals ({other / county_total:.0%}) came from patients who live in a different county "
        "than the referring practice - patient-county maps would tell a different story",
        "Location = referring provider's practice county")
    py, py_scope = recompute_python(con)
    sql = {r["provider_id"]: r["referrals_12m"] for r in d["leaderboard"]}
    scope_ok = py_scope == {p["provider_id"] for p in d["people"]}
    add("Independent Python recomputation matches SQL", "pass" if py == sql and scope_ok else "fail",
        f"{len(sql)} providers on the leaderboard, {sum(py.values()):,} referrals; scope of {len(py_scope)} people matches: {scope_ok}",
        "Same rules, different implementation")
    quiet = len(d["people"]) - len(d["leaderboard"])
    add("In-scope providers with no referral in the window", "pass",
        f"{quiet} of {len(d['people'])} in-scope providers sent nothing in the window and are not ranked",
        "Leaderboard lists referring sources only")
    return checks


# --------------------------------------------------------------------------- main
def main():
    con = P.connect()
    meta = P.meta(con)
    d = load(con)
    qa = run_qa(con, d)
    for key, name in [("leaderboard", "leaderboard"), ("trend", "monthly_trend"), ("county", "county_distribution"),
                      ("audit", "double_count_audit"), ("people", "scope_providers")]:
        P.write_csv(d[key], OUT / f"{name}.csv")
    P.write_csv(qa, OUT / "qa_results.csv")

    board = d["leaderboard"]
    total = sum(r["referrals_12m"] for r in board)
    top10 = sum(r["referrals_12m"] for r in board[:10])
    new_pt = sum(r["new_patient_referrals"] for r in board)
    shortcut = next(r for r in d["audit"] if r["method"].startswith("Specialty-bridge join, all"))
    tiles = [
        dict(label="In-scope referral providers", value=f"{len(d['people'])}", note="People carrying PUL or IMM, deduplicated"),
        dict(label="Referring in the last 12 months", value=f"{len(board)}", note="Providers with 1+ referral, Oct 2025 - Sep 2026"),
        dict(label="Referrals, 12 months", value=f"{total:,}", note=f"{new_pt:,} for new patients; duplicate faxes excluded"),
        dict(label="Top-10 share", value=f"{top10 / total:.0%}", note=f"{top10:,} of {total:,} referrals"),
        dict(label="Shortcut total", value=f"{shortcut['referrals']:,}",
             note=f"Bridge join, faxes kept: +{(shortcut['referrals'] - total) / total:.0%} vs the deduplicated count"),
    ]
    for r in board:
        r["fictional_practice"] = r["fictional_practice"].replace(" (fictional)", "")
    data = dict(meta=dict(as_of="October 24, 2026", seed=meta["seed"]), tiles=tiles, leaderboard=board, trend=d["trend"],
                county=d["county"], audit=d["audit"], qa=qa)
    P.render_dashboard(HERE / "dashboard_template.html", HERE / "dashboard.html", data)
    if P.screenshot(HERE / "dashboard.html", HERE / "dashboard.png", width=1440, height=3720):
        print("  screenshot -> dashboard.png")
    P.write_qa_log(HERE / "QA_LOG.md", "Tier 2 #09 (pulmonology/immunology referral sources)", qa)
    print(f"#09 built: {len(d['people'])} in-scope providers, {total:,} referrals; QA {P.qa_summary(qa)}")


if __name__ == "__main__":
    main()
