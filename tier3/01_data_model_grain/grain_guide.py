"""Tier 3 #01 - Data-model onboarding: grain guide, ERD and fan-out traps (SYNTHETIC).

    python tier3/01_data_model_grain/grain_guide.py

Generates GRAIN_GUIDE.md from the foundation schema (so it can never drift from the data):
every table's grain and key (with a uniqueness check), an ERD built from the declared foreign
keys, the referral-to-treatment path with row counts, and measured fan-out traps - the joins
that silently multiply rows - next to the join that keeps the grain.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "foundation"))

from shared import portfolio as P            # noqa: E402
from generator.schema import TABLES          # noqa: E402

OUT = HERE / "outputs"
PATH = [  # referral-to-treatment journey, in order
    ("patients", "A person enters the network"), ("referrals", "Each referral event (renewals, duplicate faxes included)"),
    ("orders", "Each order series (renewals start a new one)"), ("authorizations", "Each prior-authorization request"),
    ("appointments", "Each chair appointment, any status"), ("administrations", "Each medication line at a visit"),
]
TREATED = "a.status = 'Complete' AND a.meds_administered = 1"
TRAPS = [
    dict(trap="Counting patients after joining referrals", base="patients",
         naive="SELECT COUNT(*) FROM patients p JOIN referrals r ON r.patient_key = p.patient_key",
         correct="SELECT COUNT(DISTINCT p.patient_key) FROM patients p JOIN referrals r ON r.patient_key = p.patient_key",
         rule="One patient has many referrals - count DISTINCT patient_key, or aggregate referrals first"),
    dict(trap="Counting treated visits after joining administration lines", base="treated visits",
         naive=f"SELECT COUNT(*) FROM appointments a JOIN administrations ad ON ad.appt_key = a.appt_key WHERE {TREATED}",
         correct=f"""SELECT COUNT(*) FROM appointments a WHERE {TREATED}
                     AND EXISTS (SELECT 1 FROM administrations ad WHERE ad.appt_key = a.appt_key)""",
         rule="Split lots, add-on lines and duplicates give a visit several lines - use EXISTS, not JOIN"),
    dict(trap="Provider specialty through the bridge table", base="provider records",
         naive="SELECT COUNT(*) FROM providers p JOIN provider_specialties ps ON ps.provider_key = p.provider_key",
         correct="""SELECT COUNT(*) FROM providers p JOIN provider_specialties ps ON ps.provider_key = p.provider_key
                    AND ps.is_primary = 1""",
         rule="Some providers carry two specialties - filter is_primary = 1 (or use providers.primary_specialty)"),
    dict(trap="ZIP to county through the crosswalk", base="ZIP codes",
         naive="SELECT COUNT(*) FROM postal_county_crosswalk",
         correct="SELECT COUNT(*) FROM postal_county_crosswalk WHERE is_primary = 1",
         rule="ZIP 00150 straddles two counties - keep the primary-county row. No provider practices there today, "
              "so a provider join without the filter looks fine until one does (a latent bug)"),
    dict(trap="Payer for a visit without the effective date", base="treated visits",
         naive=f"SELECT COUNT(*) FROM appointments a JOIN payer_history c ON c.patient_key = a.patient_key WHERE {TREATED}",
         correct=f"""SELECT COUNT(*) FROM appointments a JOIN payer_history c ON c.patient_key = a.patient_key
                     AND c.effective_from <= date(a.start_local)
                     AND (c.effective_to IS NULL OR c.effective_to >= date(a.start_local)) WHERE {TREATED}""",
         rule="Coverage is effective-dated - join on the interval that covers the event date"),
    dict(trap="Authorization outcome from the decision events", base="authorization requests",
         naive="SELECT COUNT(*) FROM authorizations a JOIN authorization_decisions d ON d.auth_key = a.auth_key",
         correct="SELECT COUNT(*) FROM authorizations a",
         rule="Decision events include interim 'Pended' rows and duplicates - read the final outcome on the request"),
    dict(trap="Counting new patients from order series", base="patients with an order",
         naive="SELECT COUNT(*) FROM orders",
         correct="SELECT COUNT(DISTINCT patient_key) FROM orders",
         rule="Renewals and therapy changes create new order series for existing patients"),
]
BASE = {"patients": "SELECT COUNT(*) FROM patients", "treated visits": f"SELECT COUNT(*) FROM appointments a WHERE {TREATED}",
        "provider records": "SELECT COUNT(*) FROM providers", "authorization requests": "SELECT COUNT(*) FROM authorizations",
        "ZIP codes": "SELECT COUNT(DISTINCT zip5) FROM postal_county_crosswalk",
        "patients with an order": "SELECT COUNT(DISTINCT patient_key) FROM orders"}


def grain_checks(con):
    rows = []
    for name, spec in TABLES.items():
        pk = ", ".join(spec["pk"])
        n = P.scalar(con, f"SELECT COUNT(*) FROM {name}")
        distinct = P.scalar(con, f"SELECT COUNT(*) FROM (SELECT DISTINCT {pk} FROM {name})")
        rows.append(dict(table=name, family=spec["family"], grain=spec["grain"], primary_key=pk, rows=n,
                         distinct_keys=distinct, grain_holds=int(n == distinct)))
    return rows


def foreign_keys():
    return [(name, col, fk.split(".")[0], fk.split(".")[1]) for name, spec in TABLES.items()
            for col, _, _, fk in spec["columns"] if fk]


def erd():
    lines = ["```mermaid", "erDiagram"]
    for child, col, parent, _ in foreign_keys():
        lines.append(f'    {parent} ||--o{{ {child} : "{col}"')
    lines.append("```")
    return lines


def measure_traps(con):
    out = []
    for t in TRAPS:
        naive, correct, base = P.scalar(con, t["naive"]), P.scalar(con, t["correct"]), P.scalar(con, BASE[t["base"]])
        out.append(dict(trap=t["trap"], base=t["base"], base_rows=base, naive_rows=naive, correct_rows=correct,
                        naive_multiplier=round(naive / base, 2), rule=t["rule"]))
    return out


def write_guide(checks, traps, path_counts):
    lines = ["# Grain guide - synthetic infusion network data model", "",
             f"> {P.DISCLAIMER}. Generated by `grain_guide.py` from `foundation/generator/schema.py`; do not edit by hand.", "",
             "## 1. The referral-to-treatment path", "",
             "| Step | Table | Grain | Rows |", "|---|---|---|---:|"]
    for i, (name, note) in enumerate(PATH, 1):
        lines.append(f"| {i} | `{name}` | {note} | {path_counts[name]:,} |")
    lines += ["", "Every step down this path can multiply rows. Count at the grain of the question, not the grain of the last join.", "",
              "## 2. Fan-out traps (measured on the synthetic data)", "",
              "| Trap | Base | Naive join rows | Grain-safe rows | Inflation | Rule |", "|---|---:|---:|---:|---:|---|"]
    for t in traps:
        lines.append(f"| {t['trap']} | {t['base_rows']:,} {t['base']} | {t['naive_rows']:,} | {t['correct_rows']:,} | "
                     f"x{t['naive_multiplier']} | {t['rule']} |")
    payer = next(t for t in traps if t["trap"].startswith("Payer"))
    lines += ["", f"The effective-dated payer join returns {payer['correct_rows']:,} rows for {payer['base_rows']:,} treated visits: "
              f"{payer['base_rows'] - payer['correct_rows']} visits fall in a coverage gap (a planted defect for QA to find). "
              "An overlapping interval would double a visit instead. Neither is a reason to drop the date condition.", "",
              "## 3. Entity-relationship diagram (from declared foreign keys)", ""] + erd() + [
              "", "## 4. Every table: grain and key", "",
              "| Table | Family | Grain | Primary key | Rows | Key unique |", "|---|---|---|---|---:|:-:|"]
    for c in checks:
        lines.append(f"| `{c['table']}` | {c['family']} | {c['grain']} | `{c['primary_key']}` | {c['rows']:,} | "
                     f"{'yes' if c['grain_holds'] else '**NO**'} |")
    (HERE / "GRAIN_GUIDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    con = P.connect()
    checks = grain_checks(con)
    traps = measure_traps(con)
    path_counts = {name: P.scalar(con, f"SELECT COUNT(*) FROM {name}") for name, _ in PATH}
    P.write_csv(checks, OUT / "grain_checks.csv")
    P.write_csv(traps, OUT / "fanout_traps.csv")
    write_guide(checks, traps, path_counts)
    print(f"#01 built: {len(checks)} tables (grain holds: {sum(c['grain_holds'] for c in checks)}), "
          f"{len(foreign_keys())} foreign keys in the ERD, {len(traps)} fan-out traps measured")


if __name__ == "__main__":
    main()
