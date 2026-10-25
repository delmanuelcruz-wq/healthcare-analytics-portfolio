# Project registry - 21 workstreams mapped to the portfolio

> SYNTHETIC DEMONSTRATION - every dataset, chart and result in this repository is fictional.
> "Evidence status" describes the real on-the-job record as provided in the build brief. It is the ceiling for any public claim.
> Resume-safe lines marked ⚠ were tightened from the brief's suggestions so they never exceed the evidence status.

**Status key:** ✅ built and tested here · ⏸ context only (not a portfolio piece)

## Tier 1 - portfolio anchors (built)

| ID | Workstream | Evidence status (real work) | Portfolio home | Synthetic tables used | Code & QA | Resume-safe line |
|---|---|---|---|---|---|---|
| 17 | Sales executive KPI dashboard - first two reports saved | Two draft Looker reports saved Oct 24; full dashboard not built | ✅ [A](A_executive_kpi/) | patients, referrals, orders, appointments, administrations | 7 SQL files, 14 tests, 15-check QA | Built and saved two draft Looker trend reports for monthly referral intake and first administered patient treatments. |
| 18 | Referral-provider activation, dormancy, county and specialty model | Defined with manager; largely pending build | ✅ [A](A_executive_kpi/) - marked as personal extension | providers, provider_specialties, referrals, postal_county_crosswalk | rolling-90 SQL + independent Python check | ⚠ Co-defined rolling-90-day provider activation and dormancy definitions and source requirements with the analytics manager (not a completed production dashboard). |
| 13 | Ten-payer quarterly performance scorecard | Substantial Looker + Excel draft; manager required metric-definition rebuild | ✅ [B](B_payer_scorecard/) | patients, payer_history, payer_plans, payer_umbrella_map, authorizations, appointments | 8 SQL files, 10 tests, 12-check QA, Excel | ⚠ Developed a draft multi-metric payer scorecard in Looker and Excel and consolidated payer aliases; definitions under manager review. |
| 14 | Prior authorization cohort and payer approval analytics | Exploratory; cohort correction required before approval | ✅ [B](B_payer_scorecard/) - request cohort + maturity triangle | authorizations, authorization_decisions | cohort vs decision-date SQL | Investigated authorization approval metrics and revised cohort definitions based on manager feedback. |
| 15 | Patients served, PEF-to-chair and treatment mix | Looker export / Excel draft; interpretations provisional | ✅ [B](B_payer_scorecard/) | orders, appointments, administrations, calendar | NETWORKDAYS SQL + Python + Excel cross-check | Analyzed order-to-treatment lead time, served-patient cohorts and medication mix using Looker exports and Excel reconciliation (draft). |
| 02 | Weekly manufacturer inventory extraction - program A | Extensive guided / hands-on; transfer acceptance not confirmed | ✅ [C](C_manufacturer_etl_qa/) | inventory_snapshots, inventory_transactions, purchase_orders | bridge SQL, unit conversion, tests | ⚠ Prepared and validated weekly manufacturer inventory extracts (guided) using Looker exports, Excel staging and Power Query. |
| 03 | Weekly manufacturer dispense reporting - program A | Guided / hands-on | ✅ [C](C_manufacturer_etl_qa/) | administrations, appointments | dispense SQL, dedupe tests | Extracted and validated medication administration records for recurring manufacturer reporting (guided). |
| 04 | Archived orders, status progression, exception investigation | User-reported review completed | ✅ [C](C_manufacturer_etl_qa/) - rules engine | orders, order_status_events, appointments | status evidence SQL + rules engine, graded | ⚠ Investigated medication-order status exceptions case by case and applied source-based rules (cancelled-before-first-dose vs discontinued-after-dose). |
| 05 | Manufacturer program B: inventory, dispense, status | Three Excel outputs saved per run; transfer not established | ✅ [C](C_manufacturer_etl_qa/) | as 02-04 + full appointment history | history-aware injection number | Built weekly draft inventory, dispense and status workbooks using multi-pull Looker workflows and Power Query. |
| 06 | Manufacturer file QA, control totals, submission handoff | QA checklist drafted; delivery and acceptance not verified | ✅ [C](C_manufacturer_etl_qa/) - console | submission_log | batch recompute SQL, console tests | ⚠ Drafted a QA and handoff checklist for recurring manufacturer data submissions (scope, windows, control counts, escalation). |
| 11 | SharePoint license hub and nurse register | Hands-on hub work; register organized; reminders unverified | ✅ [D](D_license_compliance_hub/) | synthetic_staff, license_registry, document_index | 3 SQL files, 14 tests, Excel | ⚠ Organized a multi-state nursing license register and structured a document-library compliance hub (no live reminders claimed). |
| 12 | Medical director and site-license review | Source exports reviewed; rollout not established | ✅ [D](D_license_compliance_hub/) | site_licenses, medical_director_assignment | coverage interval checks | ⚠ Reviewed medical director and location license categories and outlined a site-to-director mapping approach. |

## Tier 2 - credibility boosters (built)

| ID | Workstream | Evidence status (real work) | Portfolio home | Synthetic tables used | Code & QA | Resume-safe line |
|---|---|---|---|---|---|---|
| 16 | CFO quarterly specialty-medication trend | Reported completed and emailed; metric-grain caution retained | ✅ [tier2/16](tier2/16_cfo_quarterly_trend/) - seven-quarter bar chart, QoQ + first-to-last, one-sheet xlsx, distinct-appointment vs line-item footnote | administrations, appointments, calendar | 2 SQL files, 6 tests, 10-check QA, Excel with live formulas | Prepared and delivered a seven-quarter specialty therapy utilization trend with a concise executive summary (self-reported). |
| 09 | Pulmonology/immunology referral-provider analysis | User reported complete; delivery not verified | ✅ [tier2/09](tier2/09_specialty_referral_sources/) - leaderboard, 12-month trend, provider-county view, location definition on the page | providers, provider_specialties, referrals, patients, crosswalk | 5 SQL files, 7 tests, 10-check QA, independent Python check | Completed a specialty referral-source reporting assignment involving geographic and provider segmentation (self-reported). |
| 10 | Medicaid J/Q-style fee schedule lookup | User-reported complete; final inventory not visible | ✅ [tier2/10](tier2/10_fee_schedule_lookup/) - code + claim type + effective date match; six exclusive buckets; Excel tracker | code_catalog, mock_fee_schedule, lookup_requests | 2 SQL files, 10 tests, 10-check QA, Python classifier | ⚠ Built a fee-schedule lookup and exception tracker for a batch of medication billing codes, separating zero-dollar rates from missing ones. |
| 19 | Appointment-goals reporting and daily refresh architecture | Recurring report assigned; automation only demonstrated | ✅ [tier2/19](tier2/19_incremental_refresh/) - **personal project**: 54 daily drops, idempotent upsert on appt_key + changed_at, audit table, late/out-of-order files, goals vs actuals | appointments, appointment_change_log, reporting_targets | 4 SQL files, 9 tests, 11-check QA, 5 proof runs | Documented refresh architecture and reporting requirements; the automated pipeline is a separate personal project. |

## Tier 3 - technical micro-cases (built)

| ID | Workstream | Evidence status (real work) | Portfolio home | Notes | Resume-safe line |
|---|---|---|---|---|---|
| 01 | Data-model onboarding and workflow mapping | Hands-on training | ✅ [tier3/01](tier3/01_data_model_grain/) - generated grain guide, ERD from 54 foreign keys, 7 measured fan-out traps | 5 tests | Completed hands-on training on a healthcare data model and referral-to-treatment workflow (training). |
| 07 | Ad hoc patient, scheduling, document and order reports | Multiple guided requests | ✅ [tier3/07](tier3/07_service_desk_tickets/) - 5 fictional tickets, SQL answers, response log | Ticket table kept in the case folder (tickets.csv), not the generator; 7 tests | Handled guided ad hoc report requests for patient, scheduling, document and order data. |
| 08 | Pharmacy delivery Explore and missing-field escalation | Field investigation; support request drafted | ✅ [tier3/08](tier3/08_field_lineage_escalation/) - failing vs quick-fix vs corrected join, null-coverage audit, issue ticket | New tables prescriptions, rx_fills, delivery_tickets (generator v1.1.0); 3 planted defect types graded; 6 tests | Investigated BI field availability for a pharmacy-delivery explore and drafted a reproducible support request. |
| 20 | Inventory vs financial-system reconciliation | Shadowed / reviewed | ✅ [tier3/20](tier3/20_inventory_accounting_recon/) - month-end operational vs accounting ledger, timing vs real-difference classes | New table accounting_ledger (generator v1.1.0); 3 planted defect types graded; 7 tests. **Learning case only** | Not a resume item - learning exposure (shadowed an inventory-to-financial-system reconciliation). |
| 21 | Ambiguous report-correction follow-up | Scope unresolved | ⏸ Not built (optional) | Not a resume item; no real names or customers in public material | - |

## Shared foundation

| Asset | Where |
|---|---|
| Generator (stdlib Python, seed 20261024) | [`foundation/generate.py`](foundation/generate.py), [`foundation/generator/`](foundation/generator/) |
| 38 synthetic tables + manifest + checksums | [`foundation/data/`](foundation/data/), [`foundation/MANIFEST.md`](foundation/MANIFEST.md) |
| Column-level dictionary | [`foundation/DATA_DICTIONARY.md`](foundation/DATA_DICTIONARY.md) |
| Ground-truth defects register (graded by tests) | [`foundation/data/exceptions_register.csv`](foundation/data/exceptions_register.csv) |
| SQLite warehouse builder (enforced PK/FK) | [`foundation/build_warehouse.py`](foundation/build_warehouse.py) |
| Foundation tests (20, incl. a guard that the 33 v1.0.0 core CSVs stay byte-identical) | [`foundation/tests/`](foundation/tests/) |
