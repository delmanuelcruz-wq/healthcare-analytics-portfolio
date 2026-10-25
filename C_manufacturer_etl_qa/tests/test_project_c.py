"""Project C tests: reconciliation math, dispense grain, rules engine grading and console diagnoses."""
import csv
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402
import importlib.util                 # noqa: E402
_spec = importlib.util.spec_from_file_location("project_c_run", HERE / "run.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

SQL = HERE / "sql"


@pytest.fixture(scope="module")
def ctx():
    con = P.connect()
    P.run_script(con, SQL / "01_staging.sql")
    bridge = P.query(con, SQL / "02_inventory_bridge.sql")
    dispense = P.query(con, SQL / "03_dispense_extract.sql")
    events = P.query(con, SQL / "04_status_evidence.sql")
    batches = P.query(con, SQL / "05_batch_recompute.sql")
    routed, cases = C.run_rules(events)
    files = C.build_files(bridge, dispense, routed)
    yield dict(con=con, bridge=bridge, dispense=dispense, routed=routed, cases=cases, batches=batches, files=files)
    con.close()


@pytest.fixture(scope="module")
def register():
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def planted(register, *types, field="record_key"):
    return {r[field] for r in register if r["defect_type"] in types}


def test_bridge_variances_are_exactly_the_unposted_adjustments(ctx, register):
    flagged = {b["snapshot_key"] for b in ctx["bridge"] if b["variance"]}
    in_window = {k for k in planted(register, "INVENTORY_UNPOSTED_ADJUSTMENT")
                 if any(b["snapshot_key"] == k for b in ctx["bridge"])}
    assert flagged == in_window


def test_carton_receipt_is_converted(ctx):
    converted = [b for b in ctx["bridge"] if b["carton_rows_converted"]]
    assert len(converted) == 1 and converted[0]["variance"] == 0


def test_dispense_has_one_row_per_appointment_product(ctx):
    keys = [(r["appt_key"], r["therapy_key"]) for r in ctx["dispense"]]
    assert len(keys) == len(set(keys))


def test_duplicate_lines_never_double_vials(ctx, register):
    dup_appts = {r[0] for r in ctx["con"].execute(
        "SELECT appt_key FROM program_lines WHERE is_exact_duplicate = 1")}
    for r in ctx["dispense"]:
        if r["appt_key"] in dup_appts:
            raw = P.scalar(ctx["con"], """SELECT SUM(vials) FROM program_lines WHERE appt_key = ? AND therapy_key = ?
                                          AND administered_flag = 1 AND is_exact_duplicate = 0""", (r["appt_key"], r["therapy_key"]))
            assert r["vials"] == raw


def test_injection_ordinal_counts_full_history(ctx):
    for r in ctx["dispense"]:
        assert r["injection_ordinal"] >= 1
        if r["injection_ordinal"] == 1:
            assert r["first_therapy_date"] == r["treatment_date"]
        else:
            assert r["first_therapy_date"] < r["treatment_date"]


def test_rules_engine_matches_planted_exceptions_exactly(ctx, register):
    escalate_events = {c["status_event_key"] for c in ctx["cases"] if c["disposition"] == "Escalate"}
    review = [c for c in ctx["cases"] if c["disposition"] == "Review"]
    backward = planted(register, "BACKWARD_STAGE")
    archived = planted(register, "ARCHIVED_THEN_TREATED")
    assert backward <= escalate_events
    assert archived == {c["order_key"] for c in ctx["cases"] if c["disposition"] == "Escalate"} - {
        c["order_key"] for c in ctx["cases"] if c["status_event_key"] in backward}
    assert planted(register, "DUP_STATUS_EVENT") == {c["status_event_key"] for c in review if c["rule"] == "Duplicate status event"}
    assert planted(register, "DISCONTINUED_WITHOUT_DOSE") == {c["order_key"] for c in review if c["rule"] == "Discontinued with no prior dose"}
    assert planted(register, "NEGATIVE_LEAD_TIME") == {c["order_key"] for c in review if c["rule"] == "Order created after its first dose"}
    corrected = planted(register, "BACKWARD_STAGE_CORRECTED")
    assert corrected <= {c["status_event_key"] for c in ctx["cases"] if c["disposition"] == "Verified"}


def test_cancelled_vs_discontinued_codes(ctx):
    for ev in ctx["routed"]:
        if ev["new_stage"] == "Cancelled" and ev["doses_before_event"] == 0:
            assert ev["manufacturer_status"] == "CANCELLED_BEFORE_FIRST_DOSE"
        if ev["new_stage"] == "Discontinued" and ev["doses_before_event"] > 0:
            assert ev["manufacturer_status"] == "DISCONTINUED_AFTER_DOSE"


def test_console_diagnoses_match_register(ctx, register):
    results = C.audit_batches(ctx["batches"], ctx["files"], ctx["bridge"], {}, {})
    diag = {r["batch_key"]: r["diagnosis"] for r in results if r["diagnosis"]}
    assert diag == {r["record_key"]: r["defect_type"] for r in register
                    if r["defect_type"] in ("WRONG_REPORTING_WEEK", "DUPLICATE_ROWS_IN_FILE")}
    header = {r["batch_key"] for r in results if any("includes the header" in t["detail"] for t in r["tests"])}
    assert header == planted(register, "CONTROL_COUNT_INCLUDES_HEADER")
    reds = {r["batch_key"] for r in results if r["overall"] == "red"}
    assert planted(register, "ACK_REJECTED_FORMAT", "ACK_STALE_PENDING") <= reds


def test_sample_package_controls_exclude_header():
    folder = HERE / "outputs" / "sample_submission"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for m in manifest["files"]:
        lines = (folder / m["file_name"]).read_text(encoding="utf-8").splitlines()
        assert m["record_count"] == max(0, len(lines) - 1)
        assert m["destination"].startswith("mock://")
        assert "PT0" not in "\n".join(lines)


def test_token_is_stable_and_one_way():
    assert C.token("PT", "PT00001") == C.token("PT", "PT00001")
    assert "PT00001" not in C.token("PT", "PT00001")
