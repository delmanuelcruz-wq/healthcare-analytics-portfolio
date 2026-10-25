"""Reference data and tuning knobs for the synthetic infusion network.

Everything in this file is invented. Organization, site, county, payer, plan,
therapy, code and staff labels are fictional and were written from scratch for
this portfolio. ZIP codes use the unassigned USPS range 00100-00499 so they can
never collide with a real address.
"""
from datetime import date

SEED = 20261024
DATA_START = date(2024, 7, 1)      # first event date in the universe
AS_OF = date(2026, 10, 24)         # snapshot date (end of day); October is partial
FUTURE_END = date(2026, 12, 31)    # furthest booked appointment

ORG_NAME = "Coralline Infusion Network (fictional)"
DISCLAIMER = "SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance"

# Clinic closure days (weekends are always closed).
HOLIDAYS = {
    date(2024, 7, 4), date(2024, 9, 2), date(2024, 11, 28), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 5, 26), date(2025, 7, 4), date(2025, 9, 1),
    date(2025, 11, 27), date(2025, 12, 25), date(2026, 1, 1), date(2026, 5, 25),
    date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
}

# --------------------------------------------------------------------------
# Geography: 14 fictional counties in three real state codes.
# (county_key, county_name, state_code, population_weight, zip5 list)
# --------------------------------------------------------------------------
COUNTIES = [
    ("CTY01", "Saltmeadow County", "GA", 0.12, ["00101", "00102", "00103"]),
    ("CTY02", "Tallow Creek County", "GA", 0.05, ["00111", "00112"]),
    ("CTY03", "Cypressmoor County", "GA", 0.10, ["00121", "00122", "00123"]),
    ("CTY04", "Wren Hollow County", "GA", 0.04, ["00131", "00132"]),
    ("CTY05", "Larkspur County", "GA", 0.07, ["00141", "00142"]),
    ("CTY06", "Heronmouth County", "SC", 0.11, ["00201", "00202", "00203"]),
    ("CTY07", "Sablecrest County", "SC", 0.08, ["00211", "00212"]),
    ("CTY08", "Indigo Flats County", "SC", 0.04, ["00221", "00222"]),
    ("CTY09", "Gullwing County", "SC", 0.06, ["00231", "00232"]),
    ("CTY10", "Brinemoor County", "NC", 0.10, ["00301", "00302", "00303"]),
    ("CTY11", "Cedar Landing County", "NC", 0.09, ["00311", "00312"]),
    ("CTY12", "Quarry Hill County", "NC", 0.05, ["00321", "00322"]),
    ("CTY13", "Palmetto Reach County", "NC", 0.04, ["00331", "00332"]),
    ("CTY14", "Ospreyford County", "NC", 0.05, ["00341", "00342"]),
]
# One ZIP straddles two counties - a classic crosswalk trap (designed edge case).
SPLIT_ZIP = ("00150", [("CTY04", 0.70, 1), ("CTY05", 0.30, 0)])

# (site_key, site_name, county_key, opened_date, chairs)
SITES = [
    ("S01", "Saltmeadow Infusion Suite", "CTY01", date(2019, 3, 4), 14),
    ("S02", "Cypressmoor Infusion Suite", "CTY03", date(2020, 6, 1), 12),
    ("S03", "Larkspur Infusion Suite", "CTY05", date(2022, 1, 10), 8),
    ("S04", "Heronmouth Infusion Suite", "CTY06", date(2018, 9, 17), 14),
    ("S05", "Sablecrest Infusion Suite", "CTY07", date(2021, 4, 5), 10),
    ("S06", "Gullwing Infusion Suite", "CTY09", date(2023, 2, 6), 8),
    ("S07", "Brinemoor Infusion Suite", "CTY10", date(2019, 11, 4), 12),
    ("S08", "Cedar Landing Infusion Suite", "CTY11", date(2025, 9, 15), 8),
]
# Which site serves patients who live in each county.
COUNTY_TO_SITE = {
    "CTY01": "S01", "CTY02": "S01", "CTY03": "S02", "CTY04": "S02", "CTY05": "S03",
    "CTY06": "S04", "CTY07": "S05", "CTY08": "S05", "CTY09": "S06",
    "CTY10": "S07", "CTY11": "S08", "CTY12": "S07", "CTY13": "S08", "CTY14": "S08",
}
FALLBACK_SITE = {"S08": "S07"}  # before S08 opened, its counties went to S07

# --------------------------------------------------------------------------
# Referring-provider specialties: (code, label, share of providers)
# --------------------------------------------------------------------------
SPECIALTIES = [
    ("RHE", "Rheumatology", 0.22),
    ("NEU", "Neurology", 0.18),
    ("GI", "Gastroenterology", 0.16),
    ("IMM", "Immunology/Allergy", 0.12),
    ("PUL", "Pulmonology", 0.10),
    ("DER", "Dermatology", 0.07),
    ("NEP", "Nephrology", 0.06),
    ("PCP", "Primary Care", 0.06),
    ("HEM", "Hematology", 0.03),
]
PRACTICE_WORDS_A = ["Tidal", "Lowcountry", "Pinewood", "Harbor", "Bayline", "Riverbend",
                    "Magnolia", "Seabreeze", "Oakmoss", "Sandhill", "Bluestem", "Marshland"]
PRACTICE_WORDS_B = {
    "RHE": "Rheumatology", "NEU": "Neurology Associates", "GI": "Digestive Health",
    "IMM": "Allergy & Immunology", "PUL": "Pulmonary Care", "DER": "Dermatology",
    "NEP": "Kidney Care", "PCP": "Family Medicine", "HEM": "Hematology Group",
}

# --------------------------------------------------------------------------
# Therapies. Labels are generic mock classes, not real products.
# interval: days between maintenance doses; loading: extra early offsets (days)
# doses: (min, max) doses per order series; vials: (min, max) per dose
# --------------------------------------------------------------------------
THERAPIES = {
    "THERAPY_A": dict(label="Immune globulin infusion (mock)", route="IV", interval=28, loading=[],
                      doses=(2, 5), vials=(2, 8), pa_rate=0.95, disc_hazard=0.020, renewal=0.50, mock_code="XJ101"),
    "THERAPY_B": dict(label="Anti-inflammatory biologic infusion (mock)", route="IV", interval=56, loading=[0, 14, 42],
                      doses=(2, 4), vials=(2, 5), pa_rate=0.90, disc_hazard=0.030, renewal=0.55, mock_code="XJ102"),
    "THERAPY_C": dict(label="Anti-CD20 infusion (mock)", route="IV", interval=182, loading=[0, 14],
                      doses=(2, 3), vials=(1, 2), pa_rate=0.95, disc_hazard=0.010, renewal=0.65, mock_code="XJ103"),
    "THERAPY_D": dict(label="Integrin-blocker infusion (mock)", route="IV", interval=28, loading=[],
                      doses=(2, 6), vials=(1, 1), pa_rate=0.90, disc_hazard=0.025, renewal=0.50, mock_code="XJ104"),
    "THERAPY_E": dict(label="IV iron replacement (mock)", route="IV", interval=7, loading=[],
                      doses=(2, 4), vials=(1, 2), pa_rate=0.80, disc_hazard=0.010, renewal=0.08, mock_code="XJ105"),
    "THERAPY_F": dict(label="Anti-IL injection (mock)", route="SC", interval=28, loading=[0, 14],
                      doses=(2, 6), vials=(1, 1), pa_rate=0.90, disc_hazard=0.030, renewal=0.50, mock_code="XJ106"),
    "THERAPY_G": dict(label="Anti-IgE injection (mock)", route="SC", interval=28, loading=[],
                      doses=(2, 6), vials=(1, 3), pa_rate=0.90, disc_hazard=0.030, renewal=0.50, mock_code="XJ107"),
    "THERAPY_H": dict(label="Bone-health injection (mock)", route="SC", interval=182, loading=[],
                      doses=(1, 2), vials=(1, 1), pa_rate=0.80, disc_hazard=0.010, renewal=0.45, mock_code="XQ201"),
    "THERAPY_I": dict(label="Complement-inhibitor infusion (mock)", route="IV", interval=14, loading=[0, 7, 14, 21],
                      doses=(3, 6), vials=(3, 4), pa_rate=0.98, disc_hazard=0.020, renewal=0.55, mock_code="XJ108"),
    "THERAPY_J": dict(label="IL-6 blocker infusion (mock)", route="IV", interval=28, loading=[],
                      doses=(2, 5), vials=(1, 3), pa_rate=0.90, disc_hazard=0.030, renewal=0.50, mock_code="XJ109"),
    # Add-on line item only (never the primary therapy of an order).
    "THERAPY_K": dict(label="Pre-medication bundle (mock)", route="IV", interval=None, loading=[],
                      doses=(0, 0), vials=(1, 1), pa_rate=0.0, disc_hazard=0.0, renewal=0.0, mock_code="XJ110"),
}
SPECIALTY_THERAPY = {
    "RHE": {"THERAPY_B": .38, "THERAPY_J": .30, "THERAPY_H": .17, "THERAPY_C": .10, "THERAPY_A": .05},
    "NEU": {"THERAPY_D": .30, "THERAPY_C": .28, "THERAPY_A": .22, "THERAPY_I": .20},
    "GI": {"THERAPY_B": .55, "THERAPY_D": .25, "THERAPY_E": .20},
    "IMM": {"THERAPY_A": .50, "THERAPY_G": .30, "THERAPY_F": .20},
    "PUL": {"THERAPY_F": .45, "THERAPY_G": .45, "THERAPY_J": .10},
    "DER": {"THERAPY_B": .50, "THERAPY_F": .50},
    "NEP": {"THERAPY_E": .45, "THERAPY_I": .35, "THERAPY_H": .20},
    "HEM": {"THERAPY_E": .55, "THERAPY_A": .30, "THERAPY_I": .15},
    "PCP": {"THERAPY_E": .55, "THERAPY_H": .45},
}
# Fictional manufacturer data-agreement programs (project C).
PROGRAMS = {
    "PROGRAM_A": {"therapies": ["THERAPY_D"], "files": ["INVENTORY", "DISPENSE"]},
    "PROGRAM_B": {"therapies": ["THERAPY_F", "THERAPY_G"], "files": ["INVENTORY", "DISPENSE", "STATUS"]},
}
VIALS_PER_CARTON = {"THERAPY_D": 10, "THERAPY_F": 10, "THERAPY_G": 10}

# --------------------------------------------------------------------------
# Payers: ten fictional umbrellas plus "Other".
# share = share of covered lives, denial = first-pass PA denial rate,
# tat = median PA turnaround in days, pa_mult scales PA requirement.
# --------------------------------------------------------------------------
PAYER_UMBRELLAS = [
    ("PU01", "Heronview Health", "Commercial", 0.16, 0.08, 6, 1.0),
    ("PU02", "Saltgrass Mutual", "Commercial", 0.12, 0.10, 8, 1.0),
    ("PU03", "Kestrel Shield Medicare Advantage", "Medicare Advantage", 0.11, 0.14, 10, 1.0),
    ("PU04", "Brightfen Advantage", "Medicare Advantage", 0.09, 0.18, 12, 1.0),
    ("PU05", "Sandmere Medicaid Plan", "Medicaid managed care", 0.08, 0.22, 14, 1.0),
    ("PU06", "Cobaltine Commercial", "Commercial", 0.08, 0.07, 5, 1.0),
    ("PU07", "Ospreyline Senior", "Medicare Advantage", 0.07, 0.12, 9, 1.0),
    ("PU08", "Driftwell Health Alliance", "Commercial / marketplace", 0.07, 0.15, 11, 1.0),
    ("PU09", "Fernhollow Care", "Medicaid managed care", 0.05, 0.20, 13, 1.0),
    ("PU10", "Quillmont Federal Medicare", "Traditional Medicare", 0.06, 0.04, 4, 0.50),
    ("PU99", "Other / small plans", "Mixed", 0.11, 0.12, 9, 0.9),
]
# Raw plan names as they appear in source systems (aliases on purpose).
# PU08 is a "plan family": three brands that must be grouped before counting.
PAYER_PLANS = {
    "PU01": [("Heronview Health PPO", .55), ("Heronview Health HMO", .35), ("HERONVIEW HEALTH", .10)],
    "PU02": [("Saltgrass Mutual PPO", .60), ("Saltgrass Mutual Choice", .30), ("Saltgrass Mut.", .10)],
    "PU03": [("Kestrel Shield MA HMO", .65), ("Kestrel Shield MA PPO", .35)],
    "PU04": [("Brightfen Advantage Plus", .80), ("Brightfen Adv. Plus", .20)],
    "PU05": [("Sandmere Medicaid Plan", .85), ("Sandmere Medicaid - LTC", .15)],
    "PU06": [("Cobaltine Commercial PPO", .70), ("Cobaltine EPO", .30)],
    "PU07": [("Ospreyline Senior Advantage", .75), ("Ospreyline Senior Adv", .25)],
    "PU08": [("Driftwell Health Alliance", .45), ("Driftwell Marketplace Silver", .35),
             ("Coastline Partners by Driftwell", .20)],
    "PU09": [("Fernhollow Care Medicaid", .80), ("Fernhollow Care Kids", .20)],
    "PU10": [("Quillmont Federal Medicare Part B", .75), ("Quillmont Medicare Supplement", .25)],
    "PU99": [("Other Commercial - Small Group", .60), ("Self-pay", .25), ("Workers Comp (mock)", .15)],
}
# Raw names that exist in source data but were never mapped (injected defect).
UNMAPPED_PLAN_ALIASES = [("Heronview Hlth PPO ", "PU01"), ("DRIFTWELL MKTPLACE", "PU08")]

REFERRAL_SOURCES = [("e-Referral portal", .45), ("Fax", .35), ("Phone intake", .10), ("Hospital discharge", .10)]
CANCEL_REASONS_PRE = [("Patient choice", .35), ("Unable to reach patient", .25), ("Referral incomplete", .20),
                      ("Physician choice", .20)]
DISCONTINUE_REASONS = [("Clinical issue", .30), ("Physician choice", .20), ("Patient choice", .20),
                       ("Therapy change", .22), ("Refusal", .08)]

# --------------------------------------------------------------------------
# Volume targets from the build brief (used by tests as soft targets).
# --------------------------------------------------------------------------
VOLUME_TARGETS = {
    "patients": 2500, "providers": 250, "referrals": 4000, "orders": 3500,
    "appointments": 9000, "administrations": 6000, "authorizations": 3200,
    "payer_history": 4000, "inventory_transactions": 4500, "license_registry": 45,
    "mock_fee_schedule": 90, "submission_log": 120,
}
