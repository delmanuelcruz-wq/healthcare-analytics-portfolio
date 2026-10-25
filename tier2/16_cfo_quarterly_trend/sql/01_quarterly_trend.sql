-- Seven-quarter utilization trend for one mock therapy (SQLite). Parameter :therapy.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
--
-- Headline grain: one treated visit = one appointment that was Complete, had medication
-- administered, and carries at least one line of this therapy actually given.
-- Quarter = calendar quarter of the SITE-LOCAL visit date (half-open: Q3 = [Jul 1, Oct 1)).
-- The line-item columns exist only to reconcile to the headline (the footnote), never to replace it.
WITH quarters AS (
    SELECT DISTINCT quarter FROM calendar WHERE quarter BETWEEN '2025-Q1' AND '2026-Q3'
),
lines AS (
    SELECT ad.admin_key, ad.appt_key, ad.administered_flag, ad.vials, a.patient_key, c.quarter,
           (a.status = 'Complete' AND a.meds_administered = 1) AS visit_treated
    FROM administrations ad
    JOIN appointments a ON a.appt_key = ad.appt_key
    JOIN calendar c ON c.cal_date = date(a.start_local)
    WHERE ad.therapy_key = :therapy
),
exact_dupes AS (   -- same appointment, lot, vials and time as an earlier line
    SELECT a.admin_key FROM administrations a
    WHERE a.therapy_key = :therapy
      AND EXISTS (SELECT 1 FROM administrations b WHERE b.appt_key = a.appt_key AND b.therapy_key = a.therapy_key
                  AND b.lot_code = a.lot_code AND b.vials = a.vials AND b.administered_at = a.administered_at
                  AND b.admin_key < a.admin_key)
)
SELECT q.quarter,
       COUNT(DISTINCT CASE WHEN l.visit_treated AND l.administered_flag = 1 THEN l.appt_key END)    AS treated_visits,
       COUNT(DISTINCT CASE WHEN l.visit_treated AND l.administered_flag = 1 THEN l.patient_key END) AS patients_treated,
       COUNT(l.admin_key)                                                                            AS line_items,
       COALESCE(SUM(l.administered_flag = 0), 0)                                                     AS waste_lines,
       COALESCE(SUM(NOT l.visit_treated AND l.administered_flag = 1), 0)                             AS given_lines_on_untreated_visits,
       COALESCE(SUM(l.visit_treated AND l.administered_flag = 1), 0)
         - COUNT(DISTINCT CASE WHEN l.visit_treated AND l.administered_flag = 1 THEN l.appt_key END)  AS extra_lines_same_visit,
       COUNT(DISTINCT CASE WHEN l.admin_key IN (SELECT admin_key FROM exact_dupes) THEN l.admin_key END) AS exact_duplicate_lines,
       COALESCE(SUM(CASE WHEN l.visit_treated AND l.administered_flag = 1 THEN l.vials END), 0)      AS vials_given
FROM quarters q
LEFT JOIN lines l ON l.quarter = q.quarter
GROUP BY q.quarter
ORDER BY q.quarter;
