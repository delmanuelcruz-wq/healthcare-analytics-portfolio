"""Tier 3 #07 tests: each ticket's SQL answers the agreed definition, checked against independent rules or the register."""
import csv
import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402

_spec = importlib.util.spec_from_file_location("tier3_t07_run", HERE / "run.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def con():
    c = P.connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def answers(con):
    return {t["ticket_id"]: M.answer(con, t) for t in M.load_tickets()}


def register(defect_types, field="record_key"):
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return {r[field] for r in csv.DictReader(fh) if r["defect_type"] in defect_types}


def test_every_ticket_has_sql_and_a_reply(answers):
    tickets = M.load_tickets()
    assert len(tickets) == 5 and set(answers) == {t["ticket_id"] for t in tickets}
    assert set(M.REPLIED_AT) == set(answers) == set(M.CAVEATS)


def test_t101_three_definitions_ordered(answers):
    active, treated, assigned = (r["patients"] for r in answers["T-101"])
    assert 0 < active < treated < assigned


def test_t102_only_booked_s04_visits_next_week(con, answers):
    rows = answers["T-102"]
    assert rows and all("2026-10-26" <= r["visit_date"] <= "2026-10-30" for r in rows)
    assert {r["booking_status"] for r in rows} <= {"Scheduled", "Confirmed"}
    sites = {P.scalar(con, "SELECT site_key FROM appointments WHERE appt_key = ?", (r["appt_key"],)) for r in rows}
    assert sites == {"S04"}


def test_t103_matches_planted_document_gaps(answers):
    assert {r["license_record_key"] for r in answers["T-103"]} == register({"LICENSE_DOC_FLAG_WRONG", "LICENSE_DOC_MISSING"})


def test_t104_ages_recomputed_in_python(con, answers):
    rows = answers["T-104"]
    assert len(rows) == P.scalar(con, "SELECT COUNT(*) FROM orders WHERE stage = 'Prior Authorization'")
    for r in rows:
        assert r["days_in_stage"] == (date(2026, 10, 24) - date.fromisoformat(r["entered_stage_at"][:10])).days


def test_t105_matches_planted_coverage_gaps(answers):
    assert {r["appt_key"] for r in answers["T-105"]} == register({"COVERAGE_GAP"}, "related_key")
    for r in answers["T-105"]:
        assert r["previous_coverage_ended"] < r["visit_date"] < r["next_coverage_starts"]


def test_answers_carry_keys_not_personal_details(answers):
    banned = re.compile(r"(name|birth|dob|phone|email|address|ssn|mrn)", re.I)
    for rows in answers.values():
        for col in rows[0]:
            assert not banned.search(col) or col in {"staff_label", "therapy_label"} or col == "payer_at_request", col
