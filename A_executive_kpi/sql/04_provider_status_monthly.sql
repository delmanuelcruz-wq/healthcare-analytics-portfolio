-- Rolling-90-day referral-provider status at each month end (plus the snapshot date).
-- Active  : >= 1 referral in (as_of - 90 days, as_of]
-- Dormant : referred at some earlier point, but none in that window
-- Never referred providers are reported separately and are NOT dormant.
-- Only referrals on or before each as_of date are visible (no future leakage).
WITH RECURSIVE month_ends(as_of) AS (
    SELECT '2025-01-31'
    UNION ALL
    SELECT date(as_of, '+1 day', '+1 month', '-1 day') FROM month_ends WHERE as_of < '2026-09-30'
),
snapshots AS (
    SELECT as_of FROM month_ends
    UNION ALL
    SELECT value FROM meta WHERE key = 'as_of_date'
),
status AS (
    SELECT s.as_of, pp.provider_id, pp.created_date,
           MIN(r.ref_date)                                                         AS first_ref,
           SUM(CASE WHEN r.ref_date > date(s.as_of, '-90 days') THEN 1 ELSE 0 END)  AS refs_90d
    FROM snapshots s
    CROSS JOIN provider_people pp
    LEFT JOIN provider_referrals r ON r.provider_id = pp.provider_id AND r.ref_date <= s.as_of
    GROUP BY s.as_of, pp.provider_id
)
SELECT as_of,
       SUM(CASE WHEN refs_90d > 0 THEN 1 ELSE 0 END)                                          AS active_providers,
       SUM(CASE WHEN refs_90d > 0 AND first_ref > date(as_of, '-90 days') THEN 1 ELSE 0 END)  AS newly_active_providers,
       SUM(CASE WHEN first_ref IS NOT NULL AND refs_90d = 0 THEN 1 ELSE 0 END)                AS dormant_providers,
       SUM(CASE WHEN first_ref IS NULL AND created_date <= as_of THEN 1 ELSE 0 END)           AS never_referred_providers,
       SUM(CASE WHEN created_date <= as_of OR first_ref IS NOT NULL THEN 1 ELSE 0 END)        AS providers_on_file
FROM status
GROUP BY as_of
ORDER BY as_of;
