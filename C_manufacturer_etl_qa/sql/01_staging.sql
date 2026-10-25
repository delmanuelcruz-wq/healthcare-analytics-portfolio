-- Project C staging (SQLite). SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
-- Fictional manufacturer data-agreement programs: PROGRAM_A (THERAPY_D), PROGRAM_B (THERAPY_F + THERAPY_G).

DROP TABLE IF EXISTS temp.program_therapy;
CREATE TEMP TABLE program_therapy AS
SELECT therapy_key, manufacturer_program AS program_key, vials_per_carton
FROM therapies WHERE manufacturer_program IS NOT NULL;

DROP TABLE IF EXISTS temp.weeks;
CREATE TEMP TABLE weeks AS
SELECT DISTINCT reporting_week_start AS week_start, date(reporting_week_start, '+7 days') AS week_end
FROM submission_log;

-- Every administration line for program therapies, with the evidence needed to clean it.
DROP TABLE IF EXISTS temp.program_lines;
CREATE TEMP TABLE program_lines AS
SELECT ad.admin_key, ad.appt_key, ad.therapy_key, pt.program_key, ad.administered_flag, ad.vials, ad.lot_code,
       ad.line_number, ad.administered_at, a.patient_key, a.order_key, a.site_key, a.start_local, a.status,
       a.meds_administered, a.updated_at,
       EXISTS (SELECT 1 FROM administrations b
               WHERE b.appt_key = ad.appt_key AND b.therapy_key = ad.therapy_key AND b.lot_code = ad.lot_code
                 AND b.vials = ad.vials AND b.administered_at = ad.administered_at
                 AND b.line_number = ad.line_number AND b.admin_key < ad.admin_key) AS is_exact_duplicate,
       CASE WHEN a.status = 'Complete' AND a.meds_administered = 1 THEN 1 ELSE 0 END AS is_valid_visit
FROM administrations ad
JOIN appointments a USING (appt_key)
JOIN program_therapy pt ON pt.therapy_key = ad.therapy_key;

-- Clean dispense grain: one row per treated appointment x therapy (duplicates removed, invalid visits out).
DROP TABLE IF EXISTS temp.program_visits;
CREATE TEMP TABLE program_visits AS
SELECT appt_key, therapy_key, program_key, patient_key, order_key, site_key, start_local,
       SUM(vials) AS vials, COUNT(*) AS lines
FROM program_lines
WHERE administered_flag = 1 AND is_exact_duplicate = 0 AND is_valid_visit = 1
GROUP BY appt_key, therapy_key;
CREATE INDEX temp.ix_pv ON program_visits(patient_key, therapy_key, start_local);

-- Payer segment at the visit (manufacturers receive a segment, never a plan or a patient name).
DROP TABLE IF EXISTS temp.visit_segment;
CREATE TEMP TABLE visit_segment AS
SELECT v.appt_key,
       COALESCE((SELECT u.segment FROM payer_history c
                 JOIN payer_umbrella_map m ON m.plan_key = c.plan_key
                 JOIN payer_umbrellas u ON u.umbrella_key = m.umbrella_key
                 WHERE c.patient_key = v.patient_key AND c.effective_from <= date(v.start_local)
                   AND (c.effective_to IS NULL OR c.effective_to >= date(v.start_local))
                 ORDER BY c.effective_from DESC LIMIT 1), 'Unknown') AS payer_segment
FROM (SELECT DISTINCT appt_key, patient_key, start_local FROM program_visits) v;
