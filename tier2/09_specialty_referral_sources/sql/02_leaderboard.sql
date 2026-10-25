-- Referral-source leaderboard: one row per provider PERSON in scope, ranked by referrals in the window.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
WITH totals AS (SELECT COUNT(*) AS n FROM scope_referrals)
SELECT RANK() OVER (ORDER BY COUNT(r.referral_key) DESC, COUNT(DISTINCT r.patient_key) DESC) AS rank,
       sp.provider_id, sp.fictional_practice, sp.specialty_group, sp.county_name, sp.state_code, sp.record_count,
       COUNT(r.referral_key)                                                      AS referrals_12m,
       COUNT(CASE WHEN r.referral_type = 'New patient' THEN 1 END)                 AS new_patient_referrals,
       COUNT(CASE WHEN r.referral_type IN ('Renewal', 'New therapy') THEN 1 END)   AS renewal_or_new_therapy,
       COUNT(DISTINCT r.patient_key)                                              AS distinct_patients,
       ROUND(1.0 * COUNT(r.referral_key) / (SELECT n FROM totals), 4)             AS share_of_scope,
       MAX(r.ref_date)                                                            AS last_referral
FROM scope_people sp
JOIN scope_referrals r ON r.provider_id = sp.provider_id
GROUP BY sp.provider_id
ORDER BY rank, sp.provider_id;
