"""Tier 3 #20 tests: every vial of difference is explained, timing reverses, real issues persist and match the register."""
import csv
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402

_spec = importlib.util.spec_from_file_location("tier3_t20_run", HERE / "run.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def built():
    con = P.connect()
    opening, events = M.load(con)
    recon, items = M.reconcile(opening, events)
    yield opening, events, recon, items
    con.close()


def planted(defect_type, field="record_key"):
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return {r[field] for r in csv.DictReader(fh) if r["defect_type"] == defect_type}


def test_systems_agree_at_the_opening_close(built):
    opening = built[0]
    assert len(opening) == 24
    assert all(r["ops_opening_vials"] == r["gl_opening_vials"] for r in opening)


def test_every_vial_is_explained(built):
    recon = built[2]
    for r in recon:
        parts = r["timing_vials"] + r["writeoff_not_booked_vials"] + r["receipt_not_invoiced_vials"] + r["duplicate_posting_vials"]
        assert r["unexplained_vials"] == 0 and parts == r["difference_vials"], (r["month_end"], r["site_key"], r["therapy_key"])


def test_planted_ledger_defects_classified_correctly(built):
    items = built[3]
    by = lambda cls: {i["inventory_event_key"] for i in items if i["classification"] == cls}   # noqa: E731
    assert by("Write-off not booked (real shortage)") == planted("GL_WRITE_OFF_NOT_BOOKED")
    assert by("Receipt not invoiced") == planted("GL_RECEIPT_NOT_INVOICED")
    assert by("Duplicate posting in accounting") == planted("GL_DUPLICATE_POSTING", "related_key")


def test_timing_items_reverse_by_next_month_end(built):
    items = built[3]
    ends = [d.isoformat() for d in M.MONTH_ENDS] + ["2026-10-31"]
    for i in items:
        if i["classification"].startswith("Timing"):
            nxt = ends[ends.index(i["month_end"]) + 1]
            assert i["first_posted"] and i["month_end"] < i["first_posted"] <= nxt, i


def test_real_issues_persist_every_later_month(built):
    items = built[3]
    real = [i for i in items if not i["classification"].startswith("Timing")]
    for key in {i["inventory_event_key"] for i in real}:
        months = sorted(i["month_end"] for i in real if i["inventory_event_key"] == key)
        assert months == [d.isoformat() for d in M.MONTH_ENDS if d.isoformat() >= months[0]], key


def test_naive_comparison_only_breaks_on_the_carton_receipt(built):
    _, events, recon, _ = built
    carton = [e for e in events if e["unit_type"] == "CARTON"]
    assert len(carton) == 1 and carton[0]["key"] in planted("INVENTORY_UNIT_MISMATCH")
    e = carton[0]
    for r in recon:
        gap = r["naive_difference_vials"] - r["difference_vials"]
        hit = (r["site_key"], r["therapy_key"]) == (e["site"], e["therapy"]) and r["month_end"] >= e["event_at"][:10]
        assert gap == ((e["recorded_qty"] - e["qty"]) if hit else 0)


def test_negative_book_inventory_persistent_means_missing_invoice_one_off_means_timing(built):
    recon = built[2]
    ends = [d.isoformat() for d in M.MONTH_ENDS]
    negative = [r for r in recon if r["gl_vials"] < 0]
    persistent = {f"{r['site_key']}|{r['therapy_key']}" for r in negative
                  if r["month_end"] != ends[-1] and any(x["gl_vials"] < 0 and x["month_end"] == ends[ends.index(r["month_end"]) + 1]
                                                        and (x["site_key"], x["therapy_key"]) == (r["site_key"], r["therapy_key"])
                                                        for x in negative)}
    assert persistent == planted("GL_RECEIPT_NOT_INVOICED", "related_key")
    for r in negative:
        if f"{r['site_key']}|{r['therapy_key']}" not in persistent:
            assert r["real_difference_vials"] == 0      # a one-off negative is an invoice still in flight
