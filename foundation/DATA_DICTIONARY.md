# Data dictionary - synthetic data foundation

> SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance. Generated from `foundation/generator/schema.py`; do not edit by hand.

## `counties`

Fictional counties used for patient home region and provider geography.

- **Grain:** one row per fictional county  
- **Primary key:** `county_key`  
- **Rows:** 14

| Column | Type | Description | References |
|---|---|---|---|
| `county_key` | TEXT | Synthetic county key |  |
| `county_name` | TEXT | Fictional county name |  |
| `state_code` | TEXT | Real two-letter state code the fictional county is placed in |  |
| `is_fictional` | INTEGER | Always 1 |  |

## `postal_county_crosswalk`

Fabricated ZIP5 codes (unassigned USPS range 00100-00499) mapped to fictional counties.

- **Grain:** one row per ZIP x county allocation  
- **Primary key:** `zip5, county_key`  
- **Rows:** 34

| Column | Type | Description | References |
|---|---|---|---|
| `zip5` | TEXT | Fabricated five-digit ZIP |  |
| `county_key` | TEXT | County the ZIP (partly) falls in | `counties.county_key` |
| `allocation_ratio` | REAL | Share of the ZIP in this county |  |
| `is_primary` | INTEGER | 1 = primary county for the ZIP; use this row to avoid duplicates |  |

## `sites`

Fictional infusion suites of the Coralline Infusion Network.

- **Grain:** one row per infusion site  
- **Primary key:** `site_key`  
- **Rows:** 8

| Column | Type | Description | References |
|---|---|---|---|
| `site_key` | TEXT | Synthetic site key |  |
| `site_name` | TEXT | Fictional site name |  |
| `county_key` | TEXT | County the site is located in | `counties.county_key` |
| `state_code` | TEXT | State code |  |
| `opened_date` | TEXT | Date the site opened (S08 opens mid-history) |  |
| `chairs` | INTEGER | Infusion chairs (capacity context only) |  |
| `timezone` | TEXT | Local timezone for appointment times |  |

## `specialties`

Referring-provider specialties.

- **Grain:** one row per specialty  
- **Primary key:** `specialty_code`  
- **Rows:** 9

| Column | Type | Description | References |
|---|---|---|---|
| `specialty_code` | TEXT | Specialty code |  |
| `specialty_label` | TEXT | Specialty name |  |

## `therapies`

Mock therapy classes (THERAPY_A..K). Not real products, doses or prices.

- **Grain:** one row per mock therapy  
- **Primary key:** `therapy_key`  
- **Rows:** 11

| Column | Type | Description | References |
|---|---|---|---|
| `therapy_key` | TEXT | Mock therapy key |  |
| `therapy_label` | TEXT | Generic mock class label |  |
| `route` | TEXT | IV infusion or SC injection |  |
| `maintenance_interval_days` | INTEGER | Typical days between maintenance doses (mock) |  |
| `is_add_on_only` | INTEGER | 1 = only appears as an add-on line item (THERAPY_K) |  |
| `manufacturer_program` | TEXT | Fictional data-agreement program, if any |  |
| `mock_billing_code` | TEXT | Mock billing code (not a real HCPCS code) |  |
| `vials_per_carton` | INTEGER | Packaging conversion for program therapies |  |

## `payer_umbrellas`

Ten fictional payer umbrellas plus an Other bucket.

- **Grain:** one row per payer umbrella  
- **Primary key:** `umbrella_key`  
- **Rows:** 11

| Column | Type | Description | References |
|---|---|---|---|
| `umbrella_key` | TEXT | Synthetic umbrella key |  |
| `umbrella_name` | TEXT | Fictional payer umbrella name |  |
| `segment` | TEXT | Commercial / Medicare Advantage / Medicaid managed care / ... |  |
| `is_top10` | INTEGER | 1 = one of the ten scorecard payers |  |

## `payer_plans`

Raw plan names, including aliases and typos that must be grouped before counting.

- **Grain:** one row per raw plan name as it appears in source  
- **Primary key:** `plan_key`  
- **Rows:** 28

| Column | Type | Description | References |
|---|---|---|---|
| `plan_key` | TEXT | Synthetic plan key |  |
| `raw_plan_name` | TEXT | Plan name as typed in the source system |  |

## `payer_umbrella_map`

Analyst-maintained alias map from raw plan to umbrella. Two aliases are deliberately missing.

- **Grain:** one row per mapped plan  
- **Primary key:** `plan_key`  
- **Rows:** 26

| Column | Type | Description | References |
|---|---|---|---|
| `plan_key` | TEXT | Raw plan | `payer_plans.plan_key` |
| `umbrella_key` | TEXT | Umbrella the plan rolls up to | `payer_umbrellas.umbrella_key` |
| `mapping_source` | TEXT | How the mapping was established |  |
| `mapped_on` | TEXT | Date mapped |  |

## `providers`

Fictional referring providers. Deduplicate on source_identity_key before counting people.

- **Grain:** one row per provider record (not per real person)  
- **Primary key:** `provider_key`  
- **Rows:** 250

| Column | Type | Description | References |
|---|---|---|---|
| `provider_key` | TEXT | Synthetic provider record key |  |
| `source_identity_key` | TEXT | Stable mock identity (MOCKNPI-); duplicates share it |  |
| `primary_specialty` | TEXT | Primary specialty code | `specialties.specialty_code` |
| `fictional_practice` | TEXT | Fictional practice name |  |
| `practice_zip5` | TEXT | Practice ZIP (fabricated) - drives provider county |  |
| `created_date` | TEXT | Date the provider record was created |  |

## `provider_specialties`

Bridge table; some providers carry two specialties.

- **Grain:** one row per provider x specialty  
- **Primary key:** `provider_key, specialty_code`  
- **Rows:** 270

| Column | Type | Description | References |
|---|---|---|---|
| `provider_key` | TEXT | Provider record | `providers.provider_key` |
| `specialty_code` | TEXT | Specialty | `specialties.specialty_code` |
| `is_primary` | INTEGER | 1 = primary specialty |  |

## `patients`

Synthetic patients. No names, birth dates, contact details or addresses exist anywhere.

- **Grain:** one row per synthetic patient  
- **Primary key:** `patient_key`  
- **Rows:** 2,502

| Column | Type | Description | References |
|---|---|---|---|
| `patient_key` | TEXT | Synthetic patient key |  |
| `created_at` | TEXT | Patient record created (business proxy for new referral intake) |  |
| `home_region_code` | TEXT | Home county (coarse geography only) | `counties.county_key` |
| `home_state` | TEXT | Home state code |  |
| `primary_site_key` | TEXT | Site serving the patient's county at intake | `sites.site_key` |
| `current_state` | TEXT | Active / Pending start / Inactive / Closed at intake, as of snapshot |  |

## `payer_history`

Effective-dated insurance intervals; use the interval covering the event date.

- **Grain:** one row per patient coverage interval  
- **Primary key:** `coverage_key`  
- **Rows:** 4,303

| Column | Type | Description | References |
|---|---|---|---|
| `coverage_key` | TEXT | Synthetic coverage interval key |  |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `plan_key` | TEXT | Raw plan | `payer_plans.plan_key` |
| `effective_from` | TEXT | First covered date (inclusive) |  |
| `effective_to` | TEXT | Last covered date (inclusive); blank = current |  |
| `coverage_rank` | TEXT | Primary (secondary coverage not modeled) |  |

## `referrals`

Referral events. One patient can have several (renewals, new therapies, duplicate faxes).

- **Grain:** one row per referral event  
- **Primary key:** `referral_key`  
- **Rows:** 3,861

| Column | Type | Description | References |
|---|---|---|---|
| `referral_key` | TEXT | Synthetic referral key |  |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `provider_key` | TEXT | Referring provider record | `providers.provider_key` |
| `referral_at` | TEXT | Referral received (local time) |  |
| `source_category` | TEXT | Intake channel |  |
| `referral_type` | TEXT | New patient / New therapy / Renewal / Duplicate |  |

## `orders`

Order series. Renewals create a new series for an existing patient, so orders != new patients.

- **Grain:** one row per medication order series  
- **Primary key:** `order_key`  
- **Rows:** 3,516

| Column | Type | Description | References |
|---|---|---|---|
| `order_key` | TEXT | Synthetic order series key |  |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `referral_key` | TEXT | Referral that triggered the order | `referrals.referral_key` |
| `therapy_key` | TEXT | Ordered therapy | `therapies.therapy_key` |
| `site_key` | TEXT | Site at order creation | `sites.site_key` |
| `order_type` | TEXT | New patient / New therapy / Renewal |  |
| `created_at` | TEXT | Order series created (PEF-to-chair start point) |  |
| `stage` | TEXT | Current stage as of snapshot |  |
| `stage_updated_at` | TEXT | When the current stage was set |  |
| `archived_at` | TEXT | When archived; archived does NOT mean treatment stopped |  |
| `terminal_reason` | TEXT | Reason for terminal stage |  |

## `order_status_events`

Order stage history. Backward moves are only valid with correction_flag = 1.

- **Grain:** one row per order stage transition  
- **Primary key:** `status_event_key`  
- **Rows:** 18,897

| Column | Type | Description | References |
|---|---|---|---|
| `status_event_key` | TEXT | Synthetic status event key |  |
| `order_key` | TEXT | Order series | `orders.order_key` |
| `previous_stage` | TEXT | Stage before the transition |  |
| `new_stage` | TEXT | Stage after the transition |  |
| `event_at` | TEXT | Transition time |  |
| `reason` | TEXT | Reason text where relevant |  |
| `correction_flag` | INTEGER | 1 = approved correction (allows a backward move) |  |

## `authorizations`

PA requests with the outcome known as of the snapshot. Appeals are new requests.

- **Grain:** one row per prior-authorization request  
- **Primary key:** `auth_key`  
- **Rows:** 3,113

| Column | Type | Description | References |
|---|---|---|---|
| `auth_key` | TEXT | Synthetic authorization request key |  |
| `order_key` | TEXT | Order series | `orders.order_key` |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `plan_key_at_request` | TEXT | Plan covering the patient on the request date | `payer_plans.plan_key` |
| `requested_at` | TEXT | Request submitted - defines the request cohort |  |
| `request_sequence` | INTEGER | 1 = first request, 2 = appeal/resubmission |  |
| `decision_at` | TEXT | Final decision time if known by snapshot |  |
| `decision_result` | TEXT | Approved / Denied if known by snapshot |  |
| `as_of_status` | TEXT | Approved / Denied / Pending as of snapshot |  |

## `authorization_decisions`

Decision events including interim 'Pended' rows and some duplicates.

- **Grain:** one row per decision event  
- **Primary key:** `decision_key`  
- **Rows:** 3,631

| Column | Type | Description | References |
|---|---|---|---|
| `decision_key` | TEXT | Synthetic decision key |  |
| `auth_key` | TEXT | Authorization request | `authorizations.auth_key` |
| `decision_at` | TEXT | Decision time |  |
| `decision_result` | TEXT | Pended - info requested / Approved / Denied |  |

## `appointments`

Chair appointments as of the snapshot, including future bookings and late-updated visits.

- **Grain:** one row per appointment  
- **Primary key:** `appt_key`  
- **Rows:** 10,246

| Column | Type | Description | References |
|---|---|---|---|
| `appt_key` | TEXT | Synthetic appointment key |  |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `order_key` | TEXT | Order series | `orders.order_key` |
| `site_key` | TEXT | Site (mandatory; a few are blank on purpose) | `sites.site_key` |
| `therapy_key` | TEXT | Therapy scheduled | `therapies.therapy_key` |
| `start_local` | TEXT | Scheduled start, site local time |  |
| `start_utc` | TEXT | Scheduled start in UTC |  |
| `booked_at` | TEXT | When the appointment was booked |  |
| `status` | TEXT | Scheduled / Confirmed / Complete / Cancelled / No Show |  |
| `meds_administered` | INTEGER | 1 = medication administered at a Complete visit |  |
| `first_patient_appt_flag` | INTEGER | System flag on the patient's first booked appointment (can be stale) |  |
| `updated_at` | TEXT | Last status change visible by snapshot (late updates happen) |  |

## `appointment_change_log`

Status history used to rebuild what any past extract would have seen.

- **Grain:** one row per appointment status change  
- **Primary key:** `change_key`  
- **Rows:** 25,729

| Column | Type | Description | References |
|---|---|---|---|
| `change_key` | TEXT | Synthetic change key |  |
| `appt_key` | TEXT | Appointment | `appointments.appt_key` |
| `changed_at` | TEXT | When the change was recorded |  |
| `change_type` | TEXT | Booked / Confirmed / Completed / Cancelled / No Show |  |
| `old_status` | TEXT | Status before |  |
| `new_status` | TEXT | Status after |  |

## `administrations`

Medication line items. Split lots and add-ons create extra lines - never count lines as visits.

- **Grain:** one row per administration line item (many per appointment allowed)  
- **Primary key:** `admin_key`  
- **Rows:** 9,424

| Column | Type | Description | References |
|---|---|---|---|
| `admin_key` | TEXT | Synthetic administration line key |  |
| `appt_key` | TEXT | Appointment | `appointments.appt_key` |
| `therapy_key` | TEXT | Therapy on this line | `therapies.therapy_key` |
| `administered_flag` | INTEGER | 1 = given to patient; 0 = prepared but not given (waste) |  |
| `vials` | INTEGER | Vials on this line (mock) |  |
| `lot_code` | TEXT | Fake lot code |  |
| `line_number` | INTEGER | Line number within the appointment |  |
| `administered_at` | TEXT | Administration time (local) |  |

## `inventory_transactions`

Signed vial movements for manufacturer-program therapies at each site.

- **Grain:** one row per inventory movement  
- **Primary key:** `inventory_event_key`  
- **Rows:** 3,777

| Column | Type | Description | References |
|---|---|---|---|
| `inventory_event_key` | TEXT | Synthetic inventory event key |  |
| `site_key` | TEXT | Site | `sites.site_key` |
| `therapy_key` | TEXT | Therapy | `therapies.therapy_key` |
| `event_at` | TEXT | Movement time |  |
| `event_type` | TEXT | RECEIPT / ADMINISTERED / ADJ_WASTE / ADJ_EXPIRED / ADJ_COUNT / RETURN_IN |  |
| `qty` | INTEGER | Signed quantity in unit_type units |  |
| `unit_type` | TEXT | VIAL (one receipt is recorded in CARTON on purpose) |  |
| `reference_key` | TEXT | PO key or administration key |  |
| `lot_code` | TEXT | Lot code where applicable |  |

## `inventory_snapshots`

Weekly system snapshot of on-hand vials (Monday open, next Monday 01:15 close).

- **Grain:** one row per site x therapy x week  
- **Primary key:** `snapshot_key`  
- **Rows:** 2,715

| Column | Type | Description | References |
|---|---|---|---|
| `snapshot_key` | TEXT | site-therapy-week composite key |  |
| `site_key` | TEXT | Site | `sites.site_key` |
| `therapy_key` | TEXT | Therapy | `therapies.therapy_key` |
| `week_start` | TEXT | Monday of the reporting week |  |
| `beginning_qty` | INTEGER | On-hand vials at week open |  |
| `ending_qty` | INTEGER | On-hand vials at week close (system count) |  |
| `snapshot_taken_at` | TEXT | When the closing count was captured |  |

## `purchase_orders`

Replenishment orders behind RECEIPT movements.

- **Grain:** one row per purchase order  
- **Primary key:** `po_key`  
- **Rows:** 333

| Column | Type | Description | References |
|---|---|---|---|
| `po_key` | TEXT | Synthetic PO key |  |
| `site_key` | TEXT | Site | `sites.site_key` |
| `therapy_key` | TEXT | Therapy | `therapies.therapy_key` |
| `ordered_at` | TEXT | Ordered |  |
| `received_at` | TEXT | Received |  |
| `cartons` | INTEGER | Cartons |  |
| `qty_vials` | INTEGER | Vials (cartons x vials_per_carton) |  |

## `synthetic_staff`

Fictional clinical staff. Labels only - no names.

- **Grain:** one row per fictional staff member  
- **Primary key:** `staff_key`  
- **Rows:** 44

| Column | Type | Description | References |
|---|---|---|---|
| `staff_key` | TEXT | Synthetic staff key |  |
| `staff_label` | TEXT | Role-number label |  |
| `role` | TEXT | Role |  |
| `home_site_key` | TEXT | Home site | `sites.site_key` |
| `employment_status` | TEXT | Employment status |  |
| `hire_date` | TEXT | Hire date |  |

## `license_registry`

Fictional professional licenses (MOCK- IDs that cannot match any real license).

- **Grain:** one row per license record  
- **Primary key:** `license_record_key`  
- **Rows:** 45

| Column | Type | Description | References |
|---|---|---|---|
| `license_record_key` | TEXT | Synthetic record key |  |
| `staff_key` | TEXT | License holder | `synthetic_staff.staff_key` |
| `fictional_license_key` | TEXT | Nonfunctional MOCK- license ID |  |
| `credential_class` | TEXT | RN / LPN / APRN / PharmD / MD |  |
| `license_scope` | TEXT | Multistate (compact, mock) or single-state |  |
| `state_code` | TEXT | Issuing state |  |
| `issue_date` | TEXT | Issue date |  |
| `expiry_date` | TEXT | Expiry date |  |
| `verified_date` | TEXT | Primary-source check date (mock) |  |
| `recorded_status` | TEXT | Status as typed in the register (can be stale) |  |
| `document_flag` | INTEGER | 1 = register says a document is on file |  |

## `document_index`

Placeholder document index (no real scans exist).

- **Grain:** one row per filed license document  
- **Primary key:** `document_key`  
- **Rows:** 40

| Column | Type | Description | References |
|---|---|---|---|
| `document_key` | TEXT | Synthetic document key |  |
| `license_record_key` | TEXT | License record | `license_registry.license_record_key` |
| `document_placeholder` | TEXT | Placeholder file name |  |
| `document_type` | TEXT | Document type |  |
| `uploaded_at` | TEXT | Upload time |  |

## `site_licenses`

Facility-level licenses and permits (mock).

- **Grain:** one row per site license  
- **Primary key:** `site_license_key`  
- **Rows:** 16

| Column | Type | Description | References |
|---|---|---|---|
| `site_license_key` | TEXT | Synthetic key |  |
| `site_key` | TEXT | Site | `sites.site_key` |
| `license_type` | TEXT | License type (mock) |  |
| `fictional_license_key` | TEXT | Nonfunctional MOCK- ID |  |
| `state_code` | TEXT | State |  |
| `issue_date` | TEXT | Issue date |  |
| `expiry_date` | TEXT | Expiry date |  |
| `document_flag` | INTEGER | 1 = document on file |  |

## `medical_director_assignment`

Many-to-many, effective-dated medical director coverage of sites.

- **Grain:** one row per director x site relationship interval  
- **Primary key:** `assignment_key`  
- **Rows:** 10

| Column | Type | Description | References |
|---|---|---|---|
| `assignment_key` | TEXT | Synthetic key |  |
| `site_key` | TEXT | Site | `sites.site_key` |
| `director_staff_key` | TEXT | Director | `synthetic_staff.staff_key` |
| `relationship_start` | TEXT | Start (inclusive) |  |
| `relationship_end` | TEXT | End (inclusive); blank = current |  |
| `is_primary` | INTEGER | 1 = primary director (one per site at a time) |  |

## `code_catalog`

Mock code catalog (XJ/XQ prefixes are not valid HCPCS formats).

- **Grain:** one row per mock billing code  
- **Primary key:** `mock_code`  
- **Rows:** 78

| Column | Type | Description | References |
|---|---|---|---|
| `mock_code` | TEXT | Mock code |  |
| `code_description` | TEXT | Description |  |
| `billing_unit` | TEXT | Billing unit |  |
| `therapy_key` | TEXT | Linked therapy | `therapies.therapy_key` |

## `mock_fee_schedule`

SYNTHETIC fee schedule. Amounts are invented and must never be read as reimbursement.

- **Grain:** one row per code x claim type x effective interval  
- **Primary key:** `fee_row_key`  
- **Rows:** 90

| Column | Type | Description | References |
|---|---|---|---|
| `fee_row_key` | TEXT | Synthetic key |  |
| `mock_code` | TEXT | Mock code | `code_catalog.mock_code` |
| `claim_type` | TEXT | Professional or Facility |  |
| `effective_from` | TEXT | Start (inclusive) |  |
| `effective_to` | TEXT | End (inclusive); blank = open |  |
| `fictional_fee_amount` | REAL | Invented amount; 0.00 = zero-pay, not 'no match' |  |
| `pricing_note` | TEXT | Pricing note |  |

## `lookup_requests`

Codes an analyst was asked to price - some absent, wrong claim type, or out of date range.

- **Grain:** one row per code lookup request  
- **Primary key:** `request_key`  
- **Rows:** 61

| Column | Type | Description | References |
|---|---|---|---|
| `request_key` | TEXT | Synthetic key |  |
| `mock_code` | TEXT | Code requested | `code_catalog.mock_code` |
| `claim_type_requested` | TEXT | Claim type requested |  |
| `service_date` | TEXT | Service date |  |
| `batch_key` | TEXT | Request batch |  |

## `reporting_targets`

Synthetic monthly completed-appointment goals for 2026.

- **Grain:** one row per site x month  
- **Primary key:** `site_key, target_month`  
- **Rows:** 96

| Column | Type | Description | References |
|---|---|---|---|
| `site_key` | TEXT | Site | `sites.site_key` |
| `target_month` | TEXT | First day of month |  |
| `completed_appointment_goal` | INTEGER | Goal (count of distinct completed appointments) |  |

## `submission_log`

What the operator logged when each weekly file was built, sent and acknowledged (mock destinations).

- **Grain:** one row per generated manufacturer file  
- **Primary key:** `batch_key`  
- **Rows:** 120

| Column | Type | Description | References |
|---|---|---|---|
| `batch_key` | TEXT | Synthetic batch key |  |
| `program_key` | TEXT | Fictional program |  |
| `file_type` | TEXT | INVENTORY / DISPENSE / STATUS |  |
| `reporting_week_start` | TEXT | Monday of the reporting week |  |
| `generated_at` | TEXT | When the file was built |  |
| `source_row_count` | INTEGER | Rows staged from source |  |
| `output_row_count` | INTEGER | Rows written to the file |  |
| `control_record_count` | INTEGER | Count written to the control file (should exclude header) |  |
| `operator_qa_state` | TEXT | QA state recorded by the operator |  |
| `transfer_status` | TEXT | Transfer status |  |
| `transfer_attempts` | INTEGER | Attempts |  |
| `sent_at` | TEXT | Sent time |  |
| `ack_state` | TEXT | Accepted / Rejected / Pending |  |
| `acknowledged_at` | TEXT | Acknowledgment time |  |
| `destination` | TEXT | Mock destination URI |  |

## `prescriptions`

Prescriptions behind specialty-pharmacy deliveries for three mock therapies (Jul 2026 onward).

- **Grain:** one row per prescription shipped by a specialty pharmacy  
- **Primary key:** `rx_key`  
- **Rows:** 201

| Column | Type | Description | References |
|---|---|---|---|
| `rx_key` | TEXT | Synthetic prescription key |  |
| `order_key` | TEXT | Order series the prescription fills | `orders.order_key` |
| `patient_key` | TEXT | Patient | `patients.patient_key` |
| `therapy_key` | TEXT | Prescribed therapy | `therapies.therapy_key` |
| `dispensing_pharmacy` | TEXT | Fictional specialty pharmacy that ships the drug |  |
| `written_date` | TEXT | Date the prescription was written (mock) |  |
| `refills_authorized` | INTEGER | Refills authorized on the prescription |  |

## `rx_fills`

Each fill is shipped for one appointment. fill_number 0 = original, 1..n = refill n.

- **Grain:** one row per prescription fill  
- **Primary key:** `fill_key`  
- **Rows:** 452

| Column | Type | Description | References |
|---|---|---|---|
| `fill_key` | TEXT | Synthetic fill key |  |
| `rx_key` | TEXT | Prescription | `prescriptions.rx_key` |
| `fill_number` | INTEGER | 0 = original fill, 1..n = refill number |  |
| `for_appt_key` | TEXT | Appointment the fill was shipped for | `appointments.appt_key` |
| `fill_date` | TEXT | Date the pharmacy filled it |  |
| `vials_dispensed` | INTEGER | Vials dispensed (mock) |  |

## `delivery_tickets`

Delivery feed from the pharmacy. fill_ref is free text: RX#### (original) or RX####-R<n> (refill n).

- **Grain:** one row per pharmacy delivery ticket  
- **Primary key:** `ticket_key`  
- **Rows:** 446

| Column | Type | Description | References |
|---|---|---|---|
| `ticket_key` | TEXT | Synthetic delivery ticket key |  |
| `fill_ref` | TEXT | Fill reference as typed by the pharmacy (not a clean foreign key) |  |
| `site_key` | TEXT | Destination site | `sites.site_key` |
| `service_level` | TEXT | Next day / 2-day (mock courier) |  |
| `shipped_at` | TEXT | Shipped |  |
| `delivery_status` | TEXT | Delivered / In transit as of snapshot |  |
| `delivered_at` | TEXT | Delivered; blank while in transit (a blank on a Delivered row is a source gap) |  |
| `received_by_role` | TEXT | Role that signed for the delivery (no names) |  |
| `cold_chain_ok` | INTEGER | 1 = temperature log within range (mock) |  |
| `tracking_ref` | TEXT | Nonfunctional mock tracking reference |  |

## `accounting_ledger`

The books' view of program-drug inventory for 2026, posted with lags. Amounts are SYNTHETIC.

- **Grain:** one row per general-ledger inventory line  
- **Primary key:** `gl_line_key`  
- **Rows:** 1,749

| Column | Type | Description | References |
|---|---|---|---|
| `gl_line_key` | TEXT | Synthetic general-ledger line key |  |
| `site_key` | TEXT | Site (cost center) | `sites.site_key` |
| `therapy_key` | TEXT | Therapy (inventory item) | `therapies.therapy_key` |
| `posting_date` | TEXT | Date the line posted to the books |  |
| `fiscal_period` | TEXT | Accounting period (YYYY-MM) |  |
| `entry_type` | TEXT | OPENING_BALANCE / RECEIPT_INVOICE / COGS_ISSUE / WASTE_WRITE_OFF / EXPIRY_WRITE_OFF / COUNT_ADJUSTMENT / RETURN_CREDIT |  |
| `source_event_key` | TEXT | Operational inventory event behind the line (blank for opening balance) | `inventory_transactions.inventory_event_key` |
| `qty_vials` | INTEGER | Signed quantity, always in vials |  |
| `fictional_unit_cost` | REAL | Invented cost per vial - SYNTHETIC, not a real price |  |
| `fictional_amount` | REAL | qty_vials x fictional_unit_cost - SYNTHETIC |  |

## `exceptions_register`

Ground truth for QA: every planted problem, where it is, and which check should catch it.

- **Grain:** one row per injected defect or designed edge case  
- **Primary key:** `exception_id`  
- **Rows:** 406

| Column | Type | Description | References |
|---|---|---|---|
| `exception_id` | TEXT | Register id |  |
| `origin` | TEXT | injected_defect or designed_edge_case |  |
| `defect_type` | TEXT | Defect / edge-case type |  |
| `table_name` | TEXT | Table |  |
| `record_key` | TEXT | Primary key of the affected row (or composite) |  |
| `related_key` | TEXT | Related key or original value |  |
| `description` | TEXT | What is wrong |  |
| `expected_check` | TEXT | Check that should catch it |  |
| `projects` | TEXT | Portfolio projects / workstreams that rely on catching it |  |
