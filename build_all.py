"""Rebuild the whole portfolio from scratch and run every test.

    python build_all.py            # data -> warehouse -> projects A-D -> Tier 2 -> Tier 3 -> landing page -> tests
    python build_all.py --no-tests

SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

STEPS = [
    ("Generate synthetic data", ["foundation/generate.py"]),
    ("Build SQLite warehouse", ["foundation/build_warehouse.py"]),
    ("Project A - executive KPIs", ["A_executive_kpi/run.py"]),
    ("Project B - payer scorecard", ["B_payer_scorecard/run.py"]),
    ("Project C - manufacturer ETL and QA", ["C_manufacturer_etl_qa/run.py"]),
    ("Project D - license compliance hub", ["D_license_compliance_hub/run.py"]),
    ("Tier 2 #16 - CFO seven-quarter trend", ["tier2/16_cfo_quarterly_trend/run.py"]),
    ("Tier 2 #09 - specialty referral sources", ["tier2/09_specialty_referral_sources/run.py"]),
    ("Tier 2 #10 - fee-schedule lookup", ["tier2/10_fee_schedule_lookup/run.py"]),
    ("Tier 2 #19 - incremental refresh", ["tier2/19_incremental_refresh/run.py"]),
    ("Tier 3 #01 - grain guide", ["tier3/01_data_model_grain/grain_guide.py"]),
    ("Tier 3 #07 - service-desk tickets", ["tier3/07_service_desk_tickets/run.py"]),
    ("Tier 3 #08 - field-lineage escalation", ["tier3/08_field_lineage_escalation/run.py"]),
    ("Tier 3 #20 - inventory reconciliation", ["tier3/20_inventory_accounting_recon/run.py"]),
    ("Case-study pages (README -> case-study.html)", ["shared/case_study.py"]),
]
TEST_DIRS = ["foundation/tests", "A_executive_kpi/tests", "B_payer_scorecard/tests",
             "C_manufacturer_etl_qa/tests", "D_license_compliance_hub/tests",
             "tier2/16_cfo_quarterly_trend/tests", "tier2/09_specialty_referral_sources/tests",
             "tier2/10_fee_schedule_lookup/tests", "tier2/19_incremental_refresh/tests",
             "tier3/01_data_model_grain/tests", "tier3/07_service_desk_tickets/tests",
             "tier3/08_field_lineage_escalation/tests", "tier3/20_inventory_accounting_recon/tests",
             "shared/tests"]


def build_index():
    from shared import portfolio as P
    P.render_dashboard(ROOT / "index_template.html", ROOT / "index.html", data={})
    print("  landing page -> index.html")


def main():
    for label, args in STEPS:
        print(f"== {label}")
        subprocess.run([sys.executable, *args], check=True, cwd=ROOT)
    build_index()
    if "--no-tests" not in sys.argv:
        print("== Tests")
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TEST_DIRS], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
