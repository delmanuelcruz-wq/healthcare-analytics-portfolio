-- Goals vs actuals from the incrementally refreshed current-state table (reads targets from `wh`).
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
-- Actual = distinct appointments whose CURRENT status is Complete, by site and site-local visit month.
-- Appointments with a blank site are shown as "Unassigned" (they have no goal) rather than silently dropped.
WITH actuals AS (
    SELECT COALESCE(site_key, 'Unassigned') AS site_key, substr(start_local, 1, 7) || '-01' AS target_month,
           COUNT(*) AS completed_appointments
    FROM appt_current
    WHERE status = 'Complete' AND start_local >= '2026-01-01' AND start_local < '2026-11-01'
    GROUP BY 1, 2
),
keys AS (
    SELECT site_key, target_month FROM wh.reporting_targets WHERE target_month < '2026-11-01'
    UNION
    SELECT site_key, target_month FROM actuals
)
SELECT k.target_month, k.site_key,
       t.completed_appointment_goal AS goal,
       COALESCE(a.completed_appointments, 0) AS actual,
       CASE WHEN t.completed_appointment_goal > 0
            THEN ROUND(1.0 * COALESCE(a.completed_appointments, 0) / t.completed_appointment_goal, 4) END AS attainment,
       CASE WHEN k.target_month = '2026-10-01' THEN 1 ELSE 0 END AS is_partial_month
FROM keys k
LEFT JOIN wh.reporting_targets t ON t.site_key = k.site_key AND t.target_month = k.target_month
LEFT JOIN actuals a ON a.site_key = k.site_key AND a.target_month = k.target_month
ORDER BY k.target_month, k.site_key;
