-- 12-month trend by specialty group, zero-filled so a quiet month shows as 0 rather than disappearing.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
WITH months AS (SELECT DISTINCT month_start FROM calendar WHERE cal_date >= '2025-10-01' AND cal_date < '2026-10-01'),
groups AS (SELECT DISTINCT specialty_group FROM scope_people)
SELECT m.month_start, g.specialty_group,
       COUNT(r.referral_key)                                       AS referrals,
       COUNT(CASE WHEN r.referral_type = 'New patient' THEN 1 END)  AS new_patient_referrals,
       COUNT(DISTINCT r.provider_id)                               AS referring_providers
FROM months m
CROSS JOIN groups g
LEFT JOIN scope_referrals r ON r.month_start = m.month_start AND r.specialty_group = g.specialty_group
GROUP BY m.month_start, g.specialty_group
ORDER BY m.month_start, g.specialty_group;
