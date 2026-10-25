"""Project D tests: renewal buckets, document audit, director coverage and the Excel tracker."""
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
_spec = importlib.util.spec_from_file_location("project_d_run", HERE / "run.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)


@pytest.fixture(scope="module")
def built():
    con = P.connect()
    as_of, staff, sites_l, md, matrix, reminders, exceptions, ov = D.build(con)
    yield dict(con=con, as_of=as_of, staff=staff, sites=sites_l, md=md, matrix=matrix, reminders=reminders,
               exceptions=exceptions, ov=ov)
    con.close()


@pytest.fixture(scope="module")
def register():
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("days,expected", [(-1, "Expired"), (0, "Due in 0-30 days"), (30, "Due in 0-30 days"),
                                           (31, "Due in 31-60 days"), (60, "Due in 31-60 days"), (61, "Due in 61-90 days"),
                                           (90, "Due in 61-90 days"), (91, "Current (90+ days)")])
def test_bucket_boundaries(days, expected):
    assert D.bucket(days) == expected


def test_status_comes_from_dates(built):
    for r in built["staff"]:
        expected = (date.fromisoformat(r["expiry_date"]) - built["as_of"]).days
        assert r["days_to_expiry"] == expected


def test_findings_match_register(built, register):
    by_code = {}
    for e in built["exceptions"]:
        by_code.setdefault(e["code"], set()).add(e["record"])
    want = lambda *t: {r["record_key"] for r in register if r["defect_type"] in t}   # noqa: E731
    assert by_code["EXPIRED_STATUS_STALE"] == want("LICENSE_EXPIRED_STATUS_ACTIVE")
    assert by_code["DOC_FLAG_WRONG"] == want("LICENSE_DOC_FLAG_WRONG")
    assert by_code["DOC_MISSING"] == want("LICENSE_DOC_MISSING", "SITE_LICENSE_DOC_MISSING")
    assert by_code["DUPLICATE"] == want("LICENSE_DUPLICATE_RECORD")
    assert by_code["EXPIRED"] == want("SITE_LICENSE_EXPIRED")
    assert by_code["MD_OVERLAP"] == want("MD_OVERLAPPING_PRIMARY")
    assert by_code["MD_UNCOVERED"] == want("MD_SITE_UNCOVERED")


def test_duplicates_excluded_from_reminders(built, register):
    dupes = {r["record_key"] for r in register if r["defect_type"] == "LICENSE_DUPLICATE_RECORD"}
    assert not dupes & {r["record"] for r in built["reminders"]}


def test_reminders_are_a_plan(built):
    assert built["reminders"] and all(r["note"].startswith("Plan only") for r in built["reminders"])
    for r in built["reminders"]:
        assert r["plan_status"] == ("Would already have been sent" if date.fromisoformat(r["reminder_date"]) <= built["as_of"] else "Scheduled")


def test_site_matrix_reflects_planted_problems(built):
    m = {row["site_key"]: row["checks"] for row in built["matrix"]}
    assert not m["S05"]["Primary medical director today"]
    assert not m["S06"]["Pharmacy permit current"]
    assert not m["S08"]["Site documents on file"]
    assert not m["S08"]["One primary director at a time"]
    assert m["S01"]["Primary medical director today"]


def test_tracker_has_live_formulas():
    from openpyxl import load_workbook
    wb = load_workbook(HERE / "license_compliance_tracker.xlsx")
    sh = wb["Clinical licenses"]
    assert str(sh["O4"].value).startswith("=J4-README!$B$3")
    assert str(sh["P4"].value).startswith("=IF(O4<0")
    assert sh.conditional_formatting, "renewal buckets should be color-coded"
    assert "SYNTHETIC" in wb["README"]["A1"].value
