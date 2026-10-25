-- How the totals would drift with the tempting shortcuts, next to the deduplicated answer.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
WITH win AS (
    SELECT r.* FROM referrals r WHERE r.referral_at >= '2025-10-01' AND r.referral_at < '2026-10-01'
),
bridge AS (   -- join referrals to every PUL/IMM specialty row of the provider RECORD
    SELECT w.referral_key, w.provider_key, w.referral_type, ps.specialty_code
    FROM win w JOIN provider_specialties ps ON ps.provider_key = w.provider_key AND ps.specialty_code IN ('PUL', 'IMM')
)
SELECT 'Specialty-bridge join, all referral types (shortcut)' AS method,
       COUNT(DISTINCT provider_key) AS provider_records_or_people, COUNT(*) AS referrals
FROM bridge
UNION ALL
SELECT 'Specialty-bridge join, duplicate faxes removed',
       COUNT(DISTINCT provider_key), COUNT(*)
FROM bridge WHERE referral_type <> 'Duplicate'
UNION ALL
SELECT 'Deduplicated people, one specialty group each (used)',
       COUNT(DISTINCT provider_id), COUNT(*)
FROM scope_referrals;
