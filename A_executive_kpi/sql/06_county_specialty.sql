-- Referral events in the trailing 12 months by the REFERRING PROVIDER's county and
-- primary specialty (not the patient's home county, not the infusion site's county).
-- Primary specialty only, so multi-specialty providers are not double-counted.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date')
SELECT pp.county_name, pp.state_code, pp.specialty_label,
       COUNT(r.referral_key)          AS referrals_12m,
       COUNT(DISTINCT r.provider_id)  AS referring_providers_12m,
       COUNT(DISTINCT CASE WHEN r.referral_type = 'New patient' THEN r.patient_key END) AS new_patients_12m
FROM provider_referrals r
JOIN provider_people pp ON pp.provider_id = r.provider_id
WHERE r.ref_date > date((SELECT d FROM as_of), '-365 days')
  AND r.ref_date <= (SELECT d FROM as_of)
GROUP BY pp.county_name, pp.state_code, pp.specialty_label
ORDER BY pp.state_code, pp.county_name, pp.specialty_label;
