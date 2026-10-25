"""Load the synthetic CSVs into a SQLite warehouse with enforced keys.

    python foundation/build_warehouse.py      # -> foundation/warehouse.sqlite

Primary keys and foreign keys come from generator/schema.py and are enforced on
load, so a successful build proves referential integrity of every table.
A `calendar` table supports business-day (NETWORKDAYS-style) lead times in SQL.
"""
import csv
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generator import config as C          # noqa: E402
from generator.schema import TABLES        # noqa: E402

DEFAULT_DB = HERE / "warehouse.sqlite"


def ddl(name, spec):
    cols = [f'  "{c}" {typ}' for c, typ, _, _ in spec["columns"]]
    cols.append(f"  PRIMARY KEY ({', '.join(spec['pk'])})")
    for c, _, _, fk in spec["columns"]:
        if fk:
            ref_table, ref_col = fk.split(".")
            cols.append(f'  FOREIGN KEY ("{c}") REFERENCES {ref_table}("{ref_col}")')
    return f'CREATE TABLE {name} (\n' + ",\n".join(cols) + "\n);"


def cast(value, typ):
    if value == "":
        return None
    if typ == "INTEGER":
        return int(value)
    if typ == "REAL":
        return float(value)
    return value


def build(db_path: Path = DEFAULT_DB, data_dir: Path = HERE / "data"):
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    with con:
        for name, spec in TABLES.items():
            con.execute(ddl(name, spec))
            types = [typ for _, typ, _, _ in spec["columns"]]
            with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                rows = [[cast(v, t) for v, t in zip(row, types)] for row in reader]
            marks = ", ".join("?" * len(header))
            con.executemany(f"INSERT INTO {name} VALUES ({marks})", rows)
        # Calendar for business-day math (weekday-only, like Excel NETWORKDAYS without a holiday list).
        con.execute("""CREATE TABLE calendar (
            cal_date TEXT PRIMARY KEY, is_weekday INTEGER, is_clinic_holiday INTEGER, is_business_day INTEGER,
            year INTEGER, quarter TEXT, month_start TEXT, week_start TEXT, weekday_seq INTEGER)""")
        d, end, seq, cal = date(2023, 1, 1), date(2027, 12, 31), 0, []
        while d <= end:
            weekday = d.weekday() < 5
            seq += 1 if weekday else 0
            cal.append((d.isoformat(), int(weekday), int(d in C.HOLIDAYS), int(weekday and d not in C.HOLIDAYS),
                        d.year, f"{d.year}-Q{(d.month - 1) // 3 + 1}", d.replace(day=1).isoformat(),
                        (d - timedelta(days=d.weekday())).isoformat(), seq))
            d += timedelta(days=1)
        con.executemany("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?)", cal)
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("as_of_date", C.AS_OF.isoformat()), ("as_of_cutoff", f"{C.AS_OF.isoformat()} 23:59:59"),
            ("seed", str(C.SEED)), ("disclaimer", C.DISCLAIMER), ("organization", C.ORG_NAME)])
        for stmt in [
            "CREATE INDEX ix_appt_patient ON appointments(patient_key, start_local)",
            "CREATE INDEX ix_appt_order ON appointments(order_key)",
            "CREATE INDEX ix_admin_appt ON administrations(appt_key)",
            "CREATE INDEX ix_ref_provider ON referrals(provider_key, referral_at)",
            "CREATE INDEX ix_cov_patient ON payer_history(patient_key, effective_from)",
            "CREATE INDEX ix_auth_order ON authorizations(order_key)",
            "CREATE INDEX ix_dec_auth ON authorization_decisions(auth_key)",
            "CREATE INDEX ix_se_order ON order_status_events(order_key, event_at)",
            "CREATE INDEX ix_inv_cell ON inventory_transactions(site_key, therapy_key, event_at)",
            "CREATE INDEX ix_gl_source ON accounting_ledger(source_event_key)",
            "CREATE INDEX ix_fill_rx ON rx_fills(rx_key, fill_number)",
        ]:
            con.execute(stmt)
    problems = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    if problems:
        raise RuntimeError(f"foreign key violations: {problems[:5]}")
    return db_path


if __name__ == "__main__":
    path = build()
    print(f"Built {path}")
