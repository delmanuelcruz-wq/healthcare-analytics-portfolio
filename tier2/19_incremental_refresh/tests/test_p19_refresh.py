"""Tier 2 #19 tests: the incremental load is idempotent, order-independent and equal to a full refresh."""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("tier2_p19_run", HERE / "run.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


@pytest.fixture(scope="module")
def run():
    con, trend = M.run_pipeline("scheduled", track=True)
    yield con, trend
    con.close()


def audit(con):
    return [dict(r) for r in con.execute("SELECT * FROM load_audit ORDER BY load_seq")]


def test_drop_files_regenerate_byte_identical(tmp_path):
    con = M.open_target()
    M.extract_drops(con, tmp_path)
    con.close()
    for d in M.drop_dates():
        assert (tmp_path / M.drop_name(d)).read_bytes() == (M.DROPS / M.drop_name(d)).read_bytes(), d


def test_incremental_equals_full_refresh(run):
    con, _ = run
    q = lambda sql: con.execute(sql).fetchone()[0]                     # noqa: E731
    assert q("""SELECT COUNT(*) FROM wh.appointments a LEFT JOIN appt_current c USING (appt_key)
                WHERE c.appt_key IS NULL OR c.status <> a.status OR c.changed_at <> a.updated_at""") == 0
    assert q("SELECT COUNT(*) FROM appt_current") == q("SELECT COUNT(*) FROM wh.appointments")
    assert q("SELECT COUNT(*) FROM appt_change_history") == q("SELECT COUNT(*) FROM wh.appointment_change_log")


def test_redelivery_inserts_and_updates_nothing(run):
    con, _ = run
    rows = [a for a in audit(con) if a["note"].startswith("Re-delivered")]
    assert len(rows) == 1 and rows[0]["rows_in_file"] > 0
    assert rows[0]["rows_inserted"] == rows[0]["appts_updated"] == rows[0]["appts_new"] == 0


def test_out_of_order_file_skips_older_changes(run):
    con, _ = run
    ooo = next(a for a in audit(con) if a["note"].startswith("Arrived after"))
    assert ooo["stale_rows_skipped"] > 0 and ooo["appts_updated"] == 0


def test_outage_files_fill_the_gap(run):
    con, _ = run
    assert sum(a["rows_inserted"] for a in audit(con) if a["note"].startswith("Sender outage")) > 0


def test_audit_arithmetic(run):
    con, _ = run
    for a in audit(con):
        assert a["rows_inserted"] + a["duplicates_ignored"] == a["rows_in_file"], a["file_name"]
    total = con.execute("SELECT SUM(rows_inserted) FROM load_audit").fetchone()[0]
    assert total == con.execute("SELECT COUNT(*) FROM appt_change_history").fetchone()[0]


def test_reruns_reloads_and_order_give_identical_tables(run):
    con, _ = run
    runs, same_full, reload_inserted = M.proofs(con)
    assert same_full and reload_inserted == 0
    assert len({r["content_sha256_12"] for r in runs}) == 1


def test_goals_vs_actuals_reconcile(run):
    con, _ = run
    gva = [dict(r) for r in con.execute((M.SQL / "03_goals_vs_actuals.sql").read_text(encoding="utf-8"))]
    direct = con.execute("""SELECT COUNT(*) FROM wh.appointments WHERE status = 'Complete'
                            AND start_local >= '2026-01-01' AND start_local < '2026-11-01'""").fetchone()[0]
    assert sum(r["actual"] for r in gva) == direct
    goals = con.execute("SELECT COUNT(*) FROM wh.reporting_targets WHERE target_month < '2026-11-01'").fetchone()[0]
    assert sum(1 for r in gva if r["goal"] is not None) == goals
    assert all(r["is_partial_month"] == (r["target_month"] == "2026-10-01") for r in gva)


def test_late_corrections_only_raise_closed_months(run):
    _, trend = run
    after_close = [t["september_completed"] for t in trend if t["arrived_at"] >= "2026-10-01 06:10:00"]
    assert after_close == sorted(after_close) and after_close[-1] > after_close[0]
    aug = [t["august_completed"] for t in trend]
    assert aug == sorted(aug) and aug[-1] > aug[0]
