"""Tier 2 #09 tests: one row per provider person, no double counting, every view reconciles."""
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402

_spec = importlib.util.spec_from_file_location("tier2_p09_run", HERE / "run.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def con():
    c = P.connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def d(con):
    return M.load(con)


@pytest.fixture(scope="module")
def register():
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_each_person_appears_once_in_one_group(d):
    ids = [r["provider_id"] for r in d["leaderboard"]]
    assert len(ids) == len(set(ids))
    groups = {p["provider_id"]: p["specialty_group"] for p in d["people"]}
    assert len(groups) == len(d["people"])


def test_dual_specialty_provider_not_double_counted(con, d):
    """PRV0201 carries both Immunology (primary) and Pulmonology (secondary): one group, referrals counted once."""
    people = {p["provider_id"]: p for p in d["people"]}
    assert people["PRV0201"]["specialty_group"] == "Immunology/Allergy"
    n = P.scalar(con, """SELECT COUNT(*) FROM referrals WHERE provider_key = 'PRV0201' AND referral_type <> 'Duplicate'
                         AND referral_at >= '2025-10-01' AND referral_at < '2026-10-01'""")
    row = next((r for r in d["leaderboard"] if r["provider_id"] == "PRV0201"), None)
    assert (row["referrals_12m"] if row else 0) == n


def test_duplicate_provider_records_roll_up(d, register):
    dupes = {r["record_key"]: r["related_key"] for r in register if r["defect_type"] == "DUPLICATE_PROVIDER_IDENTITY"}
    board = {r["provider_id"] for r in d["leaderboard"]}
    assert not (set(dupes) & board)                       # duplicate record ids never appear as their own row
    people = {p["provider_id"]: p for p in d["people"]}
    for dup, original in dupes.items():
        if original in people:
            assert people[original]["record_count"] == 2


def test_views_reconcile(con, d):
    total = P.scalar(con, "SELECT COUNT(*) FROM scope_referrals")
    assert sum(r["referrals_12m"] for r in d["leaderboard"]) == total
    assert sum(r["referrals"] for r in d["trend"]) == total
    assert sum(r["referrals_12m"] for r in d["county"]) == total
    assert d["audit"][-1]["referrals"] == total < d["audit"][1]["referrals"] < d["audit"][0]["referrals"]


def test_no_duplicate_faxes_or_out_of_window_rows(con):
    assert P.scalar(con, "SELECT COUNT(*) FROM scope_referrals WHERE referral_type = 'Duplicate'") == 0
    assert P.scalar(con, "SELECT COUNT(*) FROM scope_referrals WHERE ref_date < '2025-10-01' OR ref_date >= '2026-10-01'") == 0


def test_independent_python_matches_sql(con, d):
    py, scope = M.recompute_python(con)
    assert py == {r["provider_id"]: r["referrals_12m"] for r in d["leaderboard"]}
    assert scope == {p["provider_id"] for p in d["people"]}


def test_qa_suite_has_no_failures(con, d):
    assert not [c for c in M.run_qa(con, d) if c["status"] == "fail"]
