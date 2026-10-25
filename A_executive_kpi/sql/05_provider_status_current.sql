-- One row per referring provider (deduplicated person) as of the snapshot date.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date'),
agg AS (
    SELECT pp.provider_id,
           MIN(r.ref_date) AS first_referral,
           MAX(r.ref_date) AS last_referral,
           SUM(CASE WHEN r.ref_date > date((SELECT d FROM as_of), '-90 days') THEN 1 ELSE 0 END)  AS referrals_90d,
           SUM(CASE WHEN r.ref_date > date((SELECT d FROM as_of), '-180 days')
                     AND r.ref_date <= date((SELECT d FROM as_of), '-90 days') THEN 1 ELSE 0 END)  AS referrals_prior_90d,
           SUM(CASE WHEN r.ref_date > date((SELECT d FROM as_of), '-365 days') THEN 1 ELSE 0 END) AS referrals_12m,
           COUNT(r.referral_key) AS referrals_all_time,
           COUNT(DISTINCT CASE WHEN r.referral_type = 'New patient' THEN r.patient_key END) AS new_patients_all_time
    FROM provider_people pp
    LEFT JOIN provider_referrals r ON r.provider_id = pp.provider_id
    GROUP BY pp.provider_id
)
SELECT pp.provider_id, pp.fictional_practice, pp.specialty_label, pp.county_name, pp.state_code,
       pp.record_count, pp.created_date, a.first_referral, a.last_referral,
       a.referrals_90d, a.referrals_prior_90d, a.referrals_12m, a.referrals_all_time, a.new_patients_all_time,
       CASE WHEN a.referrals_90d > 0 THEN 'Active'
            WHEN a.first_referral IS NOT NULL THEN 'Dormant'
            ELSE 'Never referred' END                                                     AS status_90d,
       CASE WHEN a.first_referral > date((SELECT d FROM as_of), '-90 days') THEN 1 ELSE 0 END AS is_newly_active,
       CAST(julianday((SELECT d FROM as_of)) - julianday(a.last_referral) AS INTEGER)       AS days_since_last_referral
FROM provider_people pp
JOIN agg a USING (provider_id)
ORDER BY a.referrals_90d DESC, a.referrals_12m DESC, pp.provider_id;
