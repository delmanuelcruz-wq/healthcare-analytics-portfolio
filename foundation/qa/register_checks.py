"""Independent SQL detectors for every planted defect / designed edge case.

Each detector is written from the *business rule*, not from knowledge of how the
defect was injected. The foundation test grades detectors against
EXCEPTIONS_REGISTER: every planted row must be found and nothing else flagged.

compare: which register column the detector's output should match.
"""
AS_OF = "(SELECT value FROM meta WHERE key = 'as_of_cutoff')"
AS_OF_DATE = "(SELECT value FROM meta WHERE key = 'as_of_date')"
STAGE_RANK = """CASE {col} WHEN 'Intake' THEN 1 WHEN 'Benefits Verification' THEN 2
    WHEN 'Prior Authorization' THEN 3 WHEN 'Ready to Schedule' THEN 4 WHEN 'Active' THEN 5
    WHEN 'On Hold' THEN 5 ELSE 6 END"""

# Delivery feed fill reference -> (rx_key, fill_number). "RX0012" = original fill, "RX0012-R3" = refill 3.
PARSED_FILL_REF = """
    SELECT ticket_key, site_key,
           CASE WHEN instr(upper(trim(fill_ref)), '-R') > 0
                THEN substr(upper(trim(fill_ref)), 1, instr(upper(trim(fill_ref)), '-R') - 1)
                ELSE upper(trim(fill_ref)) END AS rx_key,
           CASE WHEN instr(upper(trim(fill_ref)), '-R') > 0
                THEN CAST(substr(upper(trim(fill_ref)), instr(upper(trim(fill_ref)), '-R') + 2) AS INTEGER)
                ELSE 0 END AS fill_number
    FROM delivery_tickets"""

CHECKS = {
    "DUP_ADMIN_LINE": ("record_key", """
        SELECT a.admin_key FROM administrations a
        WHERE EXISTS (SELECT 1 FROM administrations b
                      WHERE b.appt_key = a.appt_key AND b.therapy_key = a.therapy_key AND b.lot_code = a.lot_code
                        AND b.vials = a.vials AND b.administered_at = a.administered_at
                        AND b.line_number = a.line_number AND b.admin_key < a.admin_key)"""),
    "ADMIN_ON_CANCELLED_APPT": ("record_key", """
        SELECT ad.admin_key FROM administrations ad JOIN appointments ap USING (appt_key)
        WHERE ap.status IN ('Cancelled', 'No Show')"""),
    "FIRST_FLAG_DUPLICATED": ("record_key", """
        SELECT appt_key FROM (
            SELECT appt_key, ROW_NUMBER() OVER (PARTITION BY patient_key ORDER BY start_local) AS rn
            FROM appointments WHERE first_patient_appt_flag = 1) WHERE rn > 1"""),
    "TIMEZONE_MONTH_BOUNDARY": ("record_key", """
        SELECT appt_key FROM appointments WHERE substr(start_local, 1, 7) <> substr(start_utc, 1, 7)"""),
    "MISSING_SITE": ("record_key", "SELECT appt_key FROM appointments WHERE site_key IS NULL"),
    "BACKWARD_STAGE": ("record_key", f"""
        SELECT status_event_key FROM order_status_events
        WHERE previous_stage IS NOT NULL AND correction_flag = 0
          AND {STAGE_RANK.format(col='new_stage')} < {STAGE_RANK.format(col='previous_stage')}"""),
    "BACKWARD_STAGE_CORRECTED": ("record_key", f"""
        SELECT status_event_key FROM order_status_events
        WHERE previous_stage IS NOT NULL AND correction_flag = 1
          AND {STAGE_RANK.format(col='new_stage')} < {STAGE_RANK.format(col='previous_stage')}"""),
    "DUP_STATUS_EVENT": ("record_key", """
        SELECT e.status_event_key FROM order_status_events e
        WHERE EXISTS (SELECT 1 FROM order_status_events f
                      WHERE f.order_key = e.order_key AND f.new_stage = e.new_stage AND f.event_at = e.event_at
                        AND f.status_event_key < e.status_event_key)"""),
    "DISCONTINUED_WITHOUT_DOSE": ("record_key", """
        SELECT o.order_key FROM orders o
        WHERE o.stage = 'Discontinued'
          AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.order_key = o.order_key
                          AND a.status = 'Complete' AND a.meds_administered = 1)"""),
    "ARCHIVED_THEN_TREATED": ("record_key", """
        SELECT DISTINCT o.order_key FROM orders o JOIN appointments a ON a.order_key = o.order_key
        WHERE o.archived_at IS NOT NULL AND a.status = 'Complete' AND a.meds_administered = 1
          AND a.start_local > o.archived_at"""),
    "NEGATIVE_LEAD_TIME": ("record_key", """
        SELECT o.order_key FROM orders o
        JOIN (SELECT order_key, MIN(start_local) AS first_treated FROM appointments
              WHERE status = 'Complete' AND meds_administered = 1 GROUP BY order_key) f USING (order_key)
        WHERE f.first_treated < o.created_at"""),
    "DUP_AUTH_DECISION": ("record_key", """
        SELECT d.decision_key FROM authorization_decisions d
        WHERE d.decision_result IN ('Approved', 'Denied')
          AND EXISTS (SELECT 1 FROM authorization_decisions e WHERE e.auth_key = d.auth_key
                      AND e.decision_result IN ('Approved', 'Denied') AND e.decision_key < d.decision_key)"""),
    "QUARTER_BOUNDARY": ("record_key", """
        SELECT auth_key FROM authorizations
        WHERE requested_at >= '2026-06-30 22:00:00' AND requested_at < '2026-07-01 06:00:00'"""),
    "PAYER_INTERVAL_OVERLAP": ("record_key", """
        SELECT DISTINCT a.coverage_key FROM payer_history a JOIN payer_history b
          ON a.patient_key = b.patient_key AND a.coverage_key <> b.coverage_key AND a.effective_from < b.effective_from
         AND (a.effective_to IS NULL OR a.effective_to >= b.effective_from)"""),
    "COVERAGE_GAP": ("related_key", """
        SELECT a.appt_key FROM appointments a
        WHERE a.status = 'Complete' AND a.meds_administered = 1
          AND NOT EXISTS (SELECT 1 FROM payer_history c WHERE c.patient_key = a.patient_key
                          AND c.effective_from <= date(a.start_local)
                          AND (c.effective_to IS NULL OR c.effective_to >= date(a.start_local)))"""),
    "UNMAPPED_PLAN_ALIAS": ("record_key", """
        SELECT coverage_key FROM payer_history
        WHERE plan_key NOT IN (SELECT plan_key FROM payer_umbrella_map)"""),
    "DUPLICATE_PROVIDER_IDENTITY": ("record_key", """
        SELECT p.provider_key FROM providers p
        WHERE EXISTS (SELECT 1 FROM providers q WHERE q.source_identity_key = p.source_identity_key
                      AND q.provider_key < p.provider_key)"""),
    "NEVER_REFERRED_PROVIDER": ("record_key", """
        SELECT provider_key FROM providers WHERE provider_key NOT IN (SELECT provider_key FROM referrals)"""),
    "MULTI_SPECIALTY_PROVIDER": ("record_key", "SELECT provider_key FROM provider_specialties WHERE is_primary = 0"),
    "SPLIT_ZIP": ("record_key", """
        SELECT zip5 FROM postal_county_crosswalk GROUP BY zip5 HAVING COUNT(*) > 1"""),
    "LATE_UPDATE_PENDING": ("record_key", f"""
        SELECT appt_key FROM appointments WHERE start_local <= {AS_OF} AND status IN ('Scheduled', 'Confirmed')"""),
    "STALE_FIRST_FLAG": ("record_key", """
        WITH flagged AS (
            SELECT patient_key, appt_key, status, meds_administered,
                   ROW_NUMBER() OVER (PARTITION BY patient_key ORDER BY start_local) AS rn
            FROM appointments WHERE first_patient_appt_flag = 1)
        SELECT f.appt_key FROM flagged f
        WHERE f.rn = 1 AND NOT (f.status = 'Complete' AND f.meds_administered = 1)
          AND EXISTS (SELECT 1 FROM appointments a WHERE a.patient_key = f.patient_key
                      AND a.status = 'Complete' AND a.meds_administered = 1)"""),
    "INVENTORY_UNIT_MISMATCH": ("record_key", """
        SELECT inventory_event_key FROM inventory_transactions WHERE unit_type <> 'VIAL'"""),
    "INVENTORY_UNPOSTED_ADJUSTMENT": ("record_key", """
        SELECT s.snapshot_key FROM inventory_snapshots s
        LEFT JOIN (
            SELECT t.site_key, t.therapy_key, c.week_start,
                   SUM(CASE WHEN t.unit_type = 'CARTON' THEN t.qty * th.vials_per_carton ELSE t.qty END) AS net
            FROM inventory_transactions t
            JOIN calendar c ON c.cal_date = date(t.event_at)
            JOIN therapies th ON th.therapy_key = t.therapy_key
            GROUP BY 1, 2, 3) m
          ON m.site_key = s.site_key AND m.therapy_key = s.therapy_key AND m.week_start = s.week_start
        WHERE s.beginning_qty + COALESCE(m.net, 0) <> s.ending_qty"""),
    "LICENSE_EXPIRED_STATUS_ACTIVE": ("record_key", f"""
        SELECT license_record_key FROM license_registry
        WHERE expiry_date < {AS_OF_DATE} AND recorded_status = 'Active'"""),
    "LICENSE_DOC_FLAG_WRONG": ("record_key", """
        SELECT l.license_record_key FROM license_registry l
        WHERE l.document_flag = 1
          AND NOT EXISTS (SELECT 1 FROM document_index d WHERE d.license_record_key = l.license_record_key)
          AND NOT EXISTS (SELECT 1 FROM license_registry e WHERE e.fictional_license_key = l.fictional_license_key
                          AND e.license_record_key < l.license_record_key)"""),
    "LICENSE_DOC_MISSING": ("record_key", "SELECT license_record_key FROM license_registry WHERE document_flag = 0"),
    "LICENSE_DUPLICATE_RECORD": ("record_key", """
        SELECT l.license_record_key FROM license_registry l
        WHERE EXISTS (SELECT 1 FROM license_registry e WHERE e.fictional_license_key = l.fictional_license_key
                      AND e.license_record_key < l.license_record_key)"""),
    "SITE_LICENSE_EXPIRED": ("record_key", f"""
        SELECT site_license_key FROM site_licenses WHERE expiry_date < {AS_OF_DATE}"""),
    "SITE_LICENSE_DOC_MISSING": ("record_key", "SELECT site_license_key FROM site_licenses WHERE document_flag = 0"),
    "SITE_LICENSE_EXPIRING_60": ("record_key", f"""
        SELECT site_license_key FROM site_licenses
        WHERE expiry_date >= {AS_OF_DATE} AND expiry_date <= date({AS_OF_DATE}, '+60 days')"""),
    "MD_OVERLAPPING_PRIMARY": ("record_key", """
        SELECT a.assignment_key || '|' || b.assignment_key FROM medical_director_assignment a
        JOIN medical_director_assignment b ON a.site_key = b.site_key AND a.assignment_key < b.assignment_key
         AND a.is_primary = 1 AND b.is_primary = 1
         AND a.relationship_start <= COALESCE(b.relationship_end, '9999-12-31')
         AND b.relationship_start <= COALESCE(a.relationship_end, '9999-12-31')"""),
    "MD_SITE_UNCOVERED": ("related_key", f"""
        SELECT s.site_key FROM sites s
        WHERE NOT EXISTS (SELECT 1 FROM medical_director_assignment m WHERE m.site_key = s.site_key
                          AND m.is_primary = 1 AND m.relationship_start <= {AS_OF_DATE}
                          AND (m.relationship_end IS NULL OR m.relationship_end >= {AS_OF_DATE}))"""),
    "CONTROL_COUNT_INCLUDES_HEADER": ("record_key", """
        SELECT batch_key FROM submission_log WHERE control_record_count = output_row_count + 1"""),
    "ACK_REJECTED_FORMAT": ("record_key", """
        SELECT batch_key FROM submission_log WHERE ack_state = 'Rejected' AND control_record_count = output_row_count"""),
    "ACK_STALE_PENDING": ("record_key", f"""
        SELECT batch_key FROM submission_log WHERE ack_state = 'Pending' AND sent_at < datetime({AS_OF}, '-7 days')"""),
    "TRANSFER_RETRY": ("record_key", "SELECT batch_key FROM submission_log WHERE transfer_attempts > 1"),
    # ---- v1.1.0 extensions: pharmacy delivery feed (08) and accounting ledger (20)
    "DELIVERY_ORPHAN_FILL_REF": ("record_key", f"""
        WITH parsed AS ({PARSED_FILL_REF})
        SELECT p.ticket_key FROM parsed p
        WHERE NOT EXISTS (SELECT 1 FROM rx_fills f WHERE f.rx_key = p.rx_key AND f.fill_number = p.fill_number)"""),
    "DELIVERY_MISSING_DELIVERED_AT": ("record_key", """
        SELECT ticket_key FROM delivery_tickets WHERE delivery_status = 'Delivered' AND delivered_at IS NULL"""),
    "DELIVERY_WRONG_SITE": ("record_key", f"""
        WITH parsed AS ({PARSED_FILL_REF})
        SELECT p.ticket_key FROM parsed p
        JOIN rx_fills f ON f.rx_key = p.rx_key AND f.fill_number = p.fill_number
        JOIN appointments a ON a.appt_key = f.for_appt_key
        WHERE a.site_key IS NOT NULL AND a.site_key <> p.site_key"""),
    "GL_WRITE_OFF_NOT_BOOKED": ("record_key", f"""
        SELECT t.inventory_event_key FROM inventory_transactions t
        WHERE t.event_at >= '2026-01-01' AND t.event_at < datetime({AS_OF}, '-14 days')
          AND (t.event_type = 'ADJ_EXPIRED' OR (t.event_type = 'ADJ_COUNT' AND t.qty < 0))
          AND NOT EXISTS (SELECT 1 FROM accounting_ledger g WHERE g.source_event_key = t.inventory_event_key)"""),
    "GL_RECEIPT_NOT_INVOICED": ("record_key", f"""
        SELECT t.inventory_event_key FROM inventory_transactions t
        WHERE t.event_at >= '2026-01-01' AND t.event_at < datetime({AS_OF}, '-14 days') AND t.event_type = 'RECEIPT'
          AND NOT EXISTS (SELECT 1 FROM accounting_ledger g WHERE g.source_event_key = t.inventory_event_key)"""),
    "GL_DUPLICATE_POSTING": ("record_key", """
        SELECT g.gl_line_key FROM accounting_ledger g
        WHERE g.source_event_key IS NOT NULL
          AND EXISTS (SELECT 1 FROM accounting_ledger h WHERE h.source_event_key = g.source_event_key
                      AND h.entry_type = g.entry_type AND h.gl_line_key < g.gl_line_key)"""),
}

# Defects that need a recomputation of the weekly files - graded in project C.
GRADED_IN_PROJECT_C = {"WRONG_REPORTING_WEEK", "DUPLICATE_ROWS_IN_FILE"}


def run_checks(con):
    """Return {defect_type: (compare_field, set_of_keys)}."""
    return {name: (field, {row[0] for row in con.execute(sql)}) for name, (field, sql) in CHECKS.items()}
