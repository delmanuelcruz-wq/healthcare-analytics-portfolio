"""Foundation QA: reproducibility, integrity, privacy guards and graded defect detection."""
import csv
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

FOUNDATION = Path(__file__).resolve().parents[1]
DATA = FOUNDATION / "data"
sys.path.insert(0, str(FOUNDATION))

import build_warehouse                                   # noqa: E402
from generator import config as C                        # noqa: E402
from generator.schema import TABLES                      # noqa: E402
from qa.register_checks import GRADED_IN_PROJECT_C, run_checks  # noqa: E402


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    db = build_warehouse.build(tmp_path_factory.mktemp("wh") / "warehouse.sqlite", DATA)
    connection = sqlite3.connect(db)
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def register():
    with (DATA / "exceptions_register.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_regeneration_is_byte_identical(tmp_path):
    subprocess.run([sys.executable, str(FOUNDATION / "generate.py"), "--out", str(tmp_path), "--no-docs"],
                   check=True, capture_output=True)
    assert (tmp_path / "CHECKSUMS.sha256").read_text() == (DATA / "CHECKSUMS.sha256").read_text()


def test_checksums_match_files():
    import hashlib
    for line in (DATA / "CHECKSUMS.sha256").read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest, name


def test_manifest_marks_every_table_synthetic():
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert manifest["seed"] == C.SEED
    assert {t["table"] for t in manifest["tables"]} == set(TABLES)
    assert all(t["synthetic"] for t in manifest["tables"])


def test_keys_and_foreign_keys_hold(con):
    # The build enforces PK/FK on insert; this re-checks after the fact.
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    for name, spec in TABLES.items():
        pk = ", ".join(spec["pk"])
        dupes = con.execute(f"SELECT COUNT(*) FROM (SELECT {pk} FROM {name} GROUP BY {pk} HAVING COUNT(*) > 1)").fetchone()[0]
        assert dupes == 0, name


PHI_COLUMN = re.compile(r"(first_name|last_name|patient_name|full_name|dob|birth|phone|email|street|address|ssn|mrn|npi$)")
PHONE = re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")
EMAIL = re.compile(r"[\w.]+@[\w.]+\.\w+")


def test_no_phi_like_columns_or_values():
    for name, spec in TABLES.items():
        for col, *_ in spec["columns"]:
            assert not PHI_COLUMN.search(col), f"{name}.{col}"
        text = (DATA / f"{name}.csv").read_text(encoding="utf-8")
        assert not PHONE.search(text), name
        assert not EMAIL.search(text), name


def test_fabricated_identifiers_are_obviously_fake(con):
    assert con.execute("SELECT COUNT(*) FROM license_registry WHERE fictional_license_key NOT LIKE 'MOCK-%'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM providers WHERE source_identity_key NOT LIKE 'MOCKNPI-%'").fetchone()[0] == 0
    # ZIPs live in the unassigned USPS range 00100-00499
    assert con.execute("SELECT COUNT(*) FROM postal_county_crosswalk WHERE zip5 NOT BETWEEN '00100' AND '00499'").fetchone()[0] == 0


@pytest.mark.parametrize("table,tolerance", [
    ("patients", .10), ("providers", .05), ("referrals", .10), ("orders", .10), ("authorizations", .10),
    ("payer_history", .10), ("license_registry", 0), ("mock_fee_schedule", 0), ("submission_log", 0),
    ("inventory_transactions", .25),
])
def test_volumes_near_brief_targets(con, table, tolerance):
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    target = C.VOLUME_TARGETS[table]
    assert abs(n - target) <= tolerance * target, (table, n, target)


def test_event_ordering(con):
    q = lambda sql: con.execute(sql).fetchone()[0]                               # noqa: E731
    assert q("""SELECT COUNT(*) FROM patients p JOIN referrals r ON r.patient_key = p.patient_key
                AND r.referral_type = 'New patient' WHERE p.created_at < r.referral_at""") == 0
    assert q("""SELECT COUNT(*) FROM orders o JOIN referrals r USING (referral_key)
                WHERE o.created_at < r.referral_at""") == 0
    assert q("""SELECT COUNT(*) FROM authorization_decisions d JOIN authorizations a USING (auth_key)
                WHERE d.decision_at < a.requested_at""") == 0
    assert q("SELECT COUNT(*) FROM appointments WHERE booked_at >= start_local") == 0
    assert q("""SELECT COUNT(*) FROM administrations ad JOIN appointments ap USING (appt_key)
                WHERE ad.administered_at < ap.start_local""") == 0
    assert q("SELECT COUNT(*) FROM appointments WHERE booked_at > (SELECT value FROM meta WHERE key='as_of_cutoff')") == 0
    assert q("SELECT MAX(start_local) FROM appointments") <= f"{C.FUTURE_END} 23:59:59"
    # Nothing but bookings may sit after the snapshot
    for table, col in [("referrals", "referral_at"), ("orders", "created_at"), ("order_status_events", "event_at"),
                       ("authorization_decisions", "decision_at"), ("administrations", "administered_at"),
                       ("appointment_change_log", "changed_at")]:
        assert q(f"SELECT COUNT(*) FROM {table} WHERE {col} > (SELECT value FROM meta WHERE key='as_of_cutoff')") == 0, table


def test_orders_outnumber_new_patients_because_of_renewals(con):
    # The core lesson behind "use Patient Created Date, not Order Series Created Date".
    orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    renewals = con.execute("SELECT COUNT(*) FROM orders WHERE order_type = 'Renewal'").fetchone()[0]
    patients = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    assert orders > patients and renewals > 0


def test_planted_defects_are_detected_exactly(con, register):
    """Every register row is found by an independent rule, and no extra rows are flagged."""
    expected = defaultdict(lambda: {"record_key": set(), "related_key": set()})
    for row in register:
        expected[row["defect_type"]]["record_key"].add(row["record_key"])
        expected[row["defect_type"]]["related_key"].add(row["related_key"])
    detected = run_checks(con)
    missing_detector = set(expected) - set(detected) - GRADED_IN_PROJECT_C
    assert not missing_detector, missing_detector
    for defect_type, (field, found) in detected.items():
        want = expected[defect_type][field]
        assert found == want, (defect_type, sorted(want - found)[:5], sorted(found - want)[:5])


def test_v1_core_tables_unchanged_by_extensions():
    """v1.1.0 added tables on their own random streams: the 33 v1.0.0 core CSVs and the original
    393 register rows must stay byte-identical (frozen in tests/v1_core_checksums.sha256)."""
    import hashlib
    for line in (FOUNDATION / "tests" / "v1_core_checksums.sha256").read_text().splitlines():
        digest, name = line.split("  ")
        if name.endswith("[:394 lines]"):
            head = (DATA / "exceptions_register.csv").read_bytes().splitlines(keepends=True)[:394]
            assert hashlib.sha256(b"".join(head)).hexdigest() == digest, name
        else:
            assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest, name
