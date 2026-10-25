-- Project B staging (SQLite). SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.

-- Raw plan -> umbrella. Aliases missing from the map surface as UNMAPPED instead of silently dropping.
DROP TABLE IF EXISTS temp.plan_dim;
CREATE TEMP TABLE plan_dim AS
SELECT p.plan_key, p.raw_plan_name,
       COALESCE(m.umbrella_key, 'UNMAPPED')                         AS umbrella_key,
       COALESCE(u.umbrella_name, 'Unmapped alias (pending review)') AS umbrella_name
FROM payer_plans p
LEFT JOIN payer_umbrella_map m USING (plan_key)
LEFT JOIN payer_umbrellas u ON u.umbrella_key = m.umbrella_key;

DROP TABLE IF EXISTS temp.coverage;
CREATE TEMP TABLE coverage AS
SELECT c.coverage_key, c.patient_key, c.plan_key, c.effective_from, c.effective_to, d.umbrella_key
FROM payer_history c JOIN plan_dim d USING (plan_key);
CREATE INDEX temp.ix_cov ON coverage(patient_key, effective_from);

-- Same treated-visit rule as Project A.
DROP TABLE IF EXISTS temp.qualifying_visits;
CREATE TEMP TABLE qualifying_visits AS
SELECT a.appt_key, a.patient_key, a.order_key, a.therapy_key, a.start_local
FROM appointments a
WHERE a.status = 'Complete' AND a.meds_administered = 1
  AND EXISTS (SELECT 1 FROM administrations ad WHERE ad.appt_key = a.appt_key AND ad.administered_flag = 1);

-- Insurance AT THE EVENT: the interval covering the event date. If intervals overlap (a data
-- defect), the most recently started interval wins - a documented, deterministic rule.
-- No covering interval -> NO_COVERAGE (kept visible, never dropped).
DROP TABLE IF EXISTS temp.visit_payer;
CREATE TEMP TABLE visit_payer AS
SELECT v.appt_key, v.patient_key, v.order_key, v.therapy_key, v.start_local,
       (SELECT c.plan_key FROM coverage c WHERE c.patient_key = v.patient_key
          AND c.effective_from <= date(v.start_local)
          AND (c.effective_to IS NULL OR c.effective_to >= date(v.start_local))
        ORDER BY c.effective_from DESC LIMIT 1) AS plan_key
FROM qualifying_visits v;
ALTER TABLE temp.visit_payer ADD COLUMN umbrella_key TEXT;
UPDATE temp.visit_payer SET umbrella_key = COALESCE((SELECT umbrella_key FROM plan_dim d WHERE d.plan_key = visit_payer.plan_key), 'NO_COVERAGE');

DROP TABLE IF EXISTS temp.patient_payer;
CREATE TEMP TABLE patient_payer AS
SELECT p.patient_key, p.created_at,
       COALESCE((SELECT c.umbrella_key FROM coverage c WHERE c.patient_key = p.patient_key
                   AND c.effective_from <= date(p.created_at)
                   AND (c.effective_to IS NULL OR c.effective_to >= date(p.created_at))
                 ORDER BY c.effective_from DESC LIMIT 1), 'NO_COVERAGE') AS umbrella_at_intake,
       COALESCE((SELECT c.umbrella_key FROM coverage c WHERE c.patient_key = p.patient_key
                   AND c.effective_from <= (SELECT value FROM meta WHERE key = 'as_of_date')
                   AND (c.effective_to IS NULL OR c.effective_to >= (SELECT value FROM meta WHERE key = 'as_of_date'))
                 ORDER BY c.effective_from DESC LIMIT 1), 'NO_COVERAGE') AS umbrella_current
FROM patients p;

DROP TABLE IF EXISTS temp.order_payer;
CREATE TEMP TABLE order_payer AS
SELECT o.order_key, o.patient_key, o.order_type, o.therapy_key, o.created_at,
       COALESCE((SELECT c.umbrella_key FROM coverage c WHERE c.patient_key = o.patient_key
                   AND c.effective_from <= date(o.created_at)
                   AND (c.effective_to IS NULL OR c.effective_to >= date(o.created_at))
                 ORDER BY c.effective_from DESC LIMIT 1), 'NO_COVERAGE') AS umbrella_at_order
FROM orders o;

DROP TABLE IF EXISTS temp.quarters;
CREATE TEMP TABLE quarters (quarter TEXT, q_start TEXT, q_end TEXT);   -- half-open [q_start, q_end)
INSERT INTO quarters VALUES ('Q2 2026', '2026-04-01', '2026-07-01'), ('Q3 2026', '2026-07-01', '2026-10-01');

DROP TABLE IF EXISTS temp.umbrella_order;
CREATE TEMP TABLE umbrella_order AS
SELECT umbrella_key, umbrella_name, CAST(substr(umbrella_key, 3) AS INTEGER) AS sort_order FROM payer_umbrellas
UNION ALL SELECT 'UNMAPPED', 'Unmapped alias (pending review)', 100
UNION ALL SELECT 'NO_COVERAGE', 'No coverage on file at event', 101;
