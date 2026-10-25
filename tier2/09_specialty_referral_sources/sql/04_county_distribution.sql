-- Provider-county distribution. Location = the referring provider's practice county.
-- The last column shows how many of those referrals came from patients living in a DIFFERENT county,
-- which is why the location definition has to be stated on the page.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
SELECT sp.state_code, sp.county_name,
       COUNT(r.referral_key)                                                    AS referrals_12m,
       COUNT(DISTINCT r.provider_id)                                            AS referring_providers,
       COUNT(CASE WHEN r.referral_type = 'New patient' THEN 1 END)               AS new_patient_referrals,
       COUNT(CASE WHEN r.patient_county_key <> sp.county_key THEN 1 END)         AS from_patients_in_other_counties
FROM scope_referrals r
JOIN scope_people sp ON sp.provider_id = r.provider_id
GROUP BY sp.state_code, sp.county_name
ORDER BY referrals_12m DESC, sp.state_code, sp.county_name;
