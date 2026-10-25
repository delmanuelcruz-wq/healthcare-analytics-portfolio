"""Project A metric tests: each KPI definition is asserted against the synthetic warehouse."""
import csv
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402
import importlib.util                 # noqa: E402
_spec = importlib.util.spec_from_file_location("project_a_run", HERE / "run.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

SQL = HERE / "sql"


@pytest.fixture(scope="module")
def con():
    c = P.connect()
    P.run_script(c, SQL / "01_staging.sql")
    yield c
    c.close()


@pytest.fixture(scope="module")
def monthly(con):
    return P.query(con, SQL / "02_monthly_kpis.sql")


@pytest.fixture(scope="module")
def register():
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def keys(register, defect_type, field="record_key"):
    return {r[field] for r in register if r["defect_type"] == defect_type}


def test_each_patient_starts_once(con):
    assert P.scalar(con, "SELECT COUNT(*) FROM first_treatment") == \
        P.scalar(con, "SELECT COUNT(DISTINCT patient_key) FROM qualifying_visits")


def test_flag_method_never_exceeds_derived_overall(monthly):
    assert sum(r["new_treatment_starts_flag_method"] for r in monthly) < sum(r["new_treatment_starts"] for r in monthly)


def test_visits_never_exceed_line_items(monthly):
    for r in monthly:
        assert r["completed_treatment_visits"] <= r["administration_line_items"], r["month_start"]
        assert r["completed_treatment_visits"] <= r["complete_status_appointments"], r["month_start"]


def test_new_patients_differ_from_order_series(monthly):
    assert sum(r["new_order_series"] for r in monthly) > sum(r["new_referred_patients"] for r in monthly)


def test_lines_on_cancelled_appointments_are_not_treatments(con, register):
    planted = keys(register, "ADMIN_ON_CANCELLED_APPT", "related_key")
    treated = {r[0] for r in con.execute("SELECT appt_key FROM qualifying_visits")}
    assert planted and not (planted & treated)


def test_duplicate_lines_do_not_add_visits(con, register):
    dup_appts = {r[0] for r in con.execute(
        "SELECT appt_key FROM administrations WHERE admin_key IN (%s)" %
        ",".join("?" * len(keys(register, "DUP_ADMIN_LINE"))), tuple(keys(register, "DUP_ADMIN_LINE")))}
    n = P.scalar(con, "SELECT COUNT(*) FROM qualifying_visits WHERE appt_key IN (%s)" % ",".join("?" * len(dup_appts)),
                 tuple(dup_appts))
    assert n == len(dup_appts)   # each duplicated appointment still counts exactly once


def test_months_use_local_time(con, register):
    for appt in keys(register, "TIMEZONE_MONTH_BOUNDARY"):
        local_month = P.scalar(con, "SELECT month_start FROM qualifying_visits WHERE appt_key = ?", (appt,))
        start = P.scalar(con, "SELECT start_local FROM appointments WHERE appt_key = ?", (appt,))
        assert local_month == start[:7] + "-01"


def test_provider_status_partitions_and_no_future_leakage(con):
    rows = P.query(con, SQL / "04_provider_status_monthly.sql")
    for r in rows:
        assert r["active_providers"] + r["dormant_providers"] + r["never_referred_providers"] == r["providers_on_file"]
        assert r["active_providers"] == A.active_providers_python(con, date.fromisoformat(r["as_of"]))


def test_never_referred_are_not_dormant(con, register):
    current = {r["provider_id"]: r["status_90d"] for r in P.query(con, SQL / "05_provider_status_current.sql")}
    for provider in keys(register, "NEVER_REFERRED_PROVIDER"):
        if provider in current:   # duplicates of a person roll up to the earliest record
            assert current[provider] == "Never referred"


def test_duplicate_provider_records_merge(con, register):
    dupes = keys(register, "DUPLICATE_PROVIDER_IDENTITY")
    people = {r[0] for r in con.execute("SELECT provider_id FROM provider_people")}
    assert dupes and not (dupes & people)


def test_specialty_heatmap_has_no_double_counting(con):
    heat = sum(r["referrals_12m"] for r in P.query(con, SQL / "06_county_specialty.sql"))
    window = P.scalar(con, """SELECT COUNT(*) FROM referrals
                              WHERE date(referral_at) > date((SELECT value FROM meta WHERE key='as_of_date'), '-365 days')""")
    assert heat == window


def test_future_bookings_are_after_snapshot(con):
    rows = P.query(con, SQL / "03_future_bookings.sql")
    assert rows and min(r["week_start"] for r in rows) >= "2026-10-19"
    total = sum(r["booked_visits"] for r in rows)
    assert total == P.scalar(con, """SELECT COUNT(*) FROM appointments WHERE status IN ('Scheduled','Confirmed')
                                     AND start_local > (SELECT value FROM meta WHERE key='as_of_cutoff')""")


def test_funnel_is_monotonic(con):
    funnel, lead = A.summarize_cohort(P.query(con, SQL / "07_cohort_milestones.sql"), date(2026, 10, 24))
    counts = [s["patients"] for s in funnel]
    assert counts == sorted(counts, reverse=True)
    assert all(step["median_days"] is not None and step["median_days"] >= 0 for step in lead)


def test_qa_suite_has_no_failures(con, monthly):
    prov_monthly = P.query(con, SQL / "04_provider_status_monthly.sql")
    current = P.query(con, SQL / "05_provider_status_current.sql")
    heat = P.query(con, SQL / "06_county_specialty.sql")
    qa = A.run_qa(con, monthly, prov_monthly, current, heat)
    assert not [c for c in qa if c["status"] == "fail"]
