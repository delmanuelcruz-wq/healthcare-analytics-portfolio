"""Tier 3 #08 tests: the corrected join is 1:1, the quick fix fans out, and every leftover blank is a planted source defect."""
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402

_spec = importlib.util.spec_from_file_location("tier3_t08_run", HERE / "run.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def con():
    c = P.connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def runs(con):
    return M.load(con)


def planted(defect_type):
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return {r["record_key"] for r in csv.DictReader(fh) if r["defect_type"] == defect_type}


def test_corrected_join_is_one_row_per_ticket(con, runs):
    n = P.scalar(con, "SELECT COUNT(*) FROM delivery_tickets")
    keys = [r["ticket_key"] for r in runs["corrected"]]
    assert len(keys) == len(set(keys)) == n


def test_quick_fix_fans_out(runs):
    assert len(runs["quick_fix"]) > len(runs["corrected"])
    assert len({r["ticket_key"] for r in runs["quick_fix"]}) == len(runs["corrected"])


def test_as_modeled_blanks_are_exactly_the_non_bare_references(con, runs):
    blank = {r["ticket_key"] for r in runs["as_modeled"] if r["therapy_key"] is None}
    expected = {r[0] for r in con.execute(
        "SELECT ticket_key FROM delivery_tickets WHERE fill_ref NOT IN (SELECT rx_key FROM prescriptions)")}
    assert blank == expected and len(blank) > len(runs["as_modeled"]) / 2


def test_leftover_blanks_and_mismatches_are_the_planted_defects(runs):
    items, legit = M.residuals(runs)
    by = lambda issue: {i["ticket_key"] for i in items if i["issue"] == issue}   # noqa: E731
    assert by("Fill reference resolves to no fill") == planted("DELIVERY_ORPHAN_FILL_REF")
    assert by("Delivered without a delivered time") == planted("DELIVERY_MISSING_DELIVERED_AT")
    assert by("Shipped to a different site than the visit") == planted("DELIVERY_WRONG_SITE")
    assert legit and not (set(legit) & by("Delivered without a delivered time"))


def test_corrected_rows_point_at_the_right_fill(con, runs):
    for r in runs["corrected"]:
        if r["rx_key"] is None:
            continue
        expected = r["fill_ref"] if r["fill_number"] == 0 else f"{r['rx_key']}-R{r['fill_number']}"
        assert r["fill_ref"].strip().upper() == expected


def test_ticket_and_chart_written():
    text = (HERE / "ISSUE_TICKET.md").read_text(encoding="utf-8")
    for section in ("Steps to reproduce", "Root cause", "Proposed model fix", "Why not the quick fix", "Source data-quality items"):
        assert section in text
    assert (HERE / "charts" / "null_coverage.png").exists()
