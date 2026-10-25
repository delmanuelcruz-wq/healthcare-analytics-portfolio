"""Tier 3 #01 tests: every table holds its declared grain, the ERD covers every foreign key, and each trap really inflates."""
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P   # noqa: E402

_spec = importlib.util.spec_from_file_location("tier3_t01_guide", HERE / "grain_guide.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def con():
    c = P.connect()
    yield c
    c.close()


def test_every_table_holds_its_declared_grain(con):
    checks = M.grain_checks(con)
    assert len(checks) == len(M.TABLES)
    assert all(c["grain_holds"] for c in checks), [c["table"] for c in checks if not c["grain_holds"]]


def test_erd_covers_every_foreign_key():
    text = "\n".join(M.erd())
    for child, col, parent, _ in M.foreign_keys():
        assert f'{parent} ||--o{{ {child} : "{col}"' in text


def test_every_trap_inflates_and_the_safe_join_keeps_the_grain(con):
    traps = M.measure_traps(con)
    for t in traps:
        assert t["naive_rows"] > t["base_rows"], t["trap"]
        if not t["trap"].startswith("Payer"):
            assert t["correct_rows"] == t["base_rows"], t["trap"]


def test_payer_join_shortfall_is_exactly_the_planted_coverage_gaps(con):
    payer = next(t for t in M.measure_traps(con) if t["trap"].startswith("Payer"))
    with (ROOT / "foundation" / "data" / "exceptions_register.csv").open(encoding="utf-8") as fh:
        gaps = sum(1 for r in csv.DictReader(fh) if r["defect_type"] == "COVERAGE_GAP")
    assert payer["base_rows"] - payer["correct_rows"] == gaps


def test_guide_is_generated_and_complete():
    text = (HERE / "GRAIN_GUIDE.md").read_text(encoding="utf-8")
    assert "erDiagram" in text and "do not edit by hand" in text
    for name in M.TABLES:
        assert f"| `{name}` |" in text
