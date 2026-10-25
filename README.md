# Healthcare data & analytics portfolio - synthetic infusion network

> **SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.**
> Coralline Infusion Network is fictional. Every record in this repository was generated from scratch (seed `20261024`).
> No employer data, patient data, names, internal numbers or results were used, copied or used to calibrate anything.

These case studies rebuild skill areas from my September-October 2026 work in healthcare data and business intelligence
as independent, public-safe projects. Each one states plainly **what I actually did on the job** and **what I built here on
fabricated data**.

**Live site:** https://delmanuelcruz-wq.github.io/healthcare-analytics-portfolio/ - the landing page, with every dashboard one click away (source: [`index.html`](index.html)).

## Tier 1 - portfolio anchors

| | Business question | What it shows | Headline from the synthetic data |
|---|---|---|---|
| **[A · Referral-to-treatment executive KPIs](A_executive_kpi/)** | How many new patients, real treatment starts, completed visits and active referral sources? | Event-derived KPIs, rolling-90-day provider status, the grain of every count | A first-appointment-flag shortcut missed 12.3% of real treatment starts |
| **[B · Ten-payer quarterly scorecard](B_payer_scorecard/)** | How did each payer do in Q3 vs Q2? | Request-cohort authorization rates, insurance-at-event attribution, alias grouping, NETWORKDAYS lead times, a quantified revision log | Order-date "referrals" overstated new business by 48% |
| **[C · Manufacturer ETL and submission QA](C_manufacturer_etl_qa/)** | Are weekly manufacturer files right, complete and received? | Inventory bridge, deduplicated history-aware dispense file, status rules engine, control totals, submission console | Recomputing all 120 logged files exposed a wrong-week file and a duplicate-row file |
| **[D · License compliance hub](D_license_compliance_hub/)** | Can every site operate today, and what is about to lapse? | Date-computed renewal buckets, document audit, effective-dated director coverage, site matrix, Excel tracker | Only 2 of 8 sites pass all eight checks; two expired licenses were still typed "Active" |

Each Tier 1 folder has a README case study (11 sections), SQL, a build script, tests, a QA log, an interactive dashboard plus
screenshot, and a 30-second recruiter summary. Projects B and D also ship Excel workbooks with live formulas.

## Tier 2 - credibility boosters

| | Business question | What it shows | Headline from the synthetic data |
|---|---|---|---|
| **[16 · Seven-quarter therapy trend](tier2/16_cfo_quarterly_trend/)** | How has one specialty therapy grown over seven quarters? | Distinct-appointment grain, QoQ and first-to-last change, a one-sheet Excel with a native chart, a line-item reconciliation footnote | +106% from 2025 Q1 to 2026 Q3; counting line items would add 7.5% |
| **[09 · Pulmonology/immunology referral sources](tier2/09_specialty_referral_sources/)** | Who sends these patients, how is it trending, and where are they? | Deduplicated provider people, one specialty group each, explicit location definition, independent Python check | The top 10 sources send 53%; a bridge-join shortcut overstates the total by 5% |
| **[10 · Fee-schedule lookup tracker](tier2/10_fee_schedule_lookup/)** | What does the schedule pay for each requested code? | Code + claim type + effective-date matching, six exclusive buckets, $0.00 kept as zero-pay, Excel tracker | A code-only VLOOKUP gets 26 of 61 requests wrong |
| **[19 · Incremental refresh demo](tier2/19_incremental_refresh/)** | Can a daily refresh survive re-sent, late and out-of-order files? | Idempotent natural-key upsert, audit table, late corrections, five proof runs, goals vs actuals | Incremental = full refresh for all 10,246 appointments; September restated from 413 to 427 |

Tier 2 folders are shorter: README (11 sections), SQL, `run.py`, tests, a dashboard plus screenshot and a QA log.

## Tier 3 - technical micro-cases (postmortems)

| | The trap | Evidence |
|---|---|---|
| **[01 · Data-model grain guide](tier3/01_data_model_grain/)** | Joins down the referral-to-treatment chain quietly multiply rows (up to x1.75) | Generated grain guide and ERD for all 38 tables; 7 measured fan-out traps |
| **[07 · Ad hoc request desk](tier3/07_service_desk_tickets/)** | "How many patients at Saltmeadow?" has three honest answers (430, 322, 123) | 5 fictional tickets, SQL answers and a response log |
| **[08 · BI field-lineage escalation](tier3/08_field_lineage_escalation/)** | Fields blank on 71% of delivery rows - caused by the join, not the source | Failing vs corrected join, null-coverage audit, issue ticket |
| **[20 · Inventory vs accounting reconciliation](tier3/20_inventory_accounting_recon/)** | A −3-vial net difference hid 23 vials of real issues | Event-level timing vs real-difference classes (learning case) |

## One synthetic universe

All projects read the same fictional network: 2,502 patients, 250 provider records, 3,861 referrals, 3,516 order series,
10,246 appointments, payer coverage intervals, drug inventory and an accounting ledger, licenses, a mock fee schedule,
specialty-pharmacy deliveries and a submission log. That is 38 tables with enforced keys. See [`foundation/`](foundation/).

- **Reproducible:** standard-library Python and a fixed seed give byte-identical CSVs, verified by a test against [`CHECKSUMS.sha256`](foundation/data/CHECKSUMS.sha256).
- **Extended safely:** generator v1.1.0 added four tables for Tier 3 on their own random streams. A test pins the 33 original core CSVs, so they stay byte-identical.
- **Messy on purpose:** 105 injected defects and 301 designed edge cases are logged in a [ground-truth register](foundation/data/exceptions_register.csv).
  Examples: duplicate lines, late updates, unmapped payer aliases, backward status moves, missing documents, mistyped fill references, unbooked write-offs.
- **Graded QA:** independent SQL detectors must find every planted row and nothing else.

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python build_all.py               # data -> warehouse -> Tier 1 -> Tier 2 -> Tier 3 -> landing page -> tests
```

The generator needs only Python 3.12. Dashboards load Plotly from a pinned CDN.

## Quality at a glance

| Suite | Tests | Result |
|---|---:|---|
| Foundation (reproducibility, keys, privacy guards, graded defect detection, v1 core guard) | 20 | pass |
| Project A | 14 | pass |
| Project B | 10 | pass |
| Project C | 10 | pass |
| Project D | 14 | pass |
| Tier 2 (#16 · #09 · #10 · #19) | 32 | pass |
| Tier 3 (#01 · #07 · #08 · #20) | 25 | pass |
| **Total** | **125** | **pass** |

## Honesty and privacy rules this repository follows

- Fictional organization, sites, counties, payers, products, pharmacies and staff labels. ZIP codes come from the unassigned USPS range; license IDs start with `MOCK-`.
- No patient-like fields (names, birth dates, contact details, addresses) exist anywhere. A test enforces this.
- Colleagues and stakeholders appear only as roles ("analytics manager", "sales leader", "finance executive").
- Draft, guided, shadowed and planned work is described as exactly that. Nothing here says "deployed" or claims an employer outcome.
  The refresh pipeline (#19) is a personal project, and the reconciliation (#20) is a learning case.
- The mapping of all 21 workstreams, with evidence status and resume-safe wording, is in [`PROJECT_REGISTRY.md`](PROJECT_REGISTRY.md).

## Repository layout

```
foundation/                       generator (stdlib), 38 CSVs, manifest, checksums, register, warehouse builder, tests
shared/                           dashboard CSS/JS and Python helpers used by every project
A_executive_kpi/ ... D_license_compliance_hub/   Tier 1: sql/ · run.py · tests/ · dashboard · README · QA_LOG (+ Excel in B, D)
tier2/16_cfo_quarterly_trend/     sql/ · run.py · tests/ · dashboard · cfo_seven_quarter_trend.xlsx · chart · README · QA_LOG
tier2/09_specialty_referral_sources/   sql/ · run.py · tests/ · dashboard · README · QA_LOG
tier2/10_fee_schedule_lookup/     sql/ · run.py · tests/ · dashboard · fee_lookup_tracker.xlsx · README · QA_LOG
tier2/19_incremental_refresh/     sql/ · run.py · tests/ · drops/ (54 daily CSVs) · dashboard · README · QA_LOG
tier3/01_data_model_grain/        grain_guide.py · GRAIN_GUIDE.md (generated) · tests/ · README
tier3/07_service_desk_tickets/    tickets.csv · sql/ · run.py · RESPONSE_LOG.md · tests/ · README
tier3/08_field_lineage_escalation/   sql/ · run.py · ISSUE_TICKET.md · chart · tests/ · README
tier3/20_inventory_accounting_recon/ sql/ · run.py · chart · tests/ · README
PROJECT_REGISTRY.md               all 21 workstreams -> where they live, status, resume-safe language
build_all.py                      one-command rebuild
```
