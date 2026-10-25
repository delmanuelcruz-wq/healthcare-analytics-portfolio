-- Tier 2 #09 staging (SQLite). Pulmonology / immunology referral sources.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
--
-- Window: 12 full months, Oct 1, 2025 to Sep 30, 2026 (half-open). October 2026 is partial at the
-- Oct 24 snapshot and is left out. Location = the REFERRING PROVIDER's practice county (practice ZIP,
-- primary crosswalk row) - not the patient's home county and not the infusion site's county.

-- One row per provider record, with a person-level id (duplicate records share a source identity).
DROP TABLE IF EXISTS temp.provider_identity;
CREATE TEMP TABLE provider_identity AS
SELECT p.provider_key,
       MIN(p.provider_key) OVER (PARTITION BY p.source_identity_key) AS provider_id,
       p.primary_specialty, p.fictional_practice, x.county_key, c.county_name, c.state_code
FROM providers p
LEFT JOIN postal_county_crosswalk x ON x.zip5 = p.practice_zip5 AND x.is_primary = 1
LEFT JOIN counties c ON c.county_key = x.county_key;

-- Provider people in scope: ANY of their records carries Pulmonology or Immunology/Allergy, primary
-- or secondary. Each person appears once, in exactly one specialty group (their primary specialty),
-- so a provider with both specialties is never counted twice.
DROP TABLE IF EXISTS temp.scope_people;
CREATE TEMP TABLE scope_people AS
SELECT pi.provider_id, pi.fictional_practice, pi.primary_specialty, pi.county_key, pi.county_name, pi.state_code,
       CASE pi.primary_specialty WHEN 'PUL' THEN 'Pulmonology' WHEN 'IMM' THEN 'Immunology/Allergy'
            ELSE 'PUL/IMM as secondary specialty' END AS specialty_group,
       (SELECT COUNT(*) FROM provider_identity q WHERE q.provider_id = pi.provider_id) AS record_count
FROM provider_identity pi
WHERE pi.provider_key = pi.provider_id
  AND EXISTS (SELECT 1 FROM provider_identity q JOIN provider_specialties ps ON ps.provider_key = q.provider_key
              WHERE q.provider_id = pi.provider_id AND ps.specialty_code IN ('PUL', 'IMM'));

-- Referral events from those people in the window. Duplicate faxes (referral_type = 'Duplicate')
-- are the same referral received twice and are excluded from every count.
DROP TABLE IF EXISTS temp.scope_referrals;
CREATE TEMP TABLE scope_referrals AS
SELECT r.referral_key, sp.provider_id, sp.specialty_group, r.patient_key, r.referral_type,
       date(r.referral_at) AS ref_date, substr(r.referral_at, 1, 7) || '-01' AS month_start,
       pt.home_region_code AS patient_county_key
FROM referrals r
JOIN provider_identity pi ON pi.provider_key = r.provider_key
JOIN scope_people sp ON sp.provider_id = pi.provider_id
JOIN patients pt ON pt.patient_key = r.patient_key
WHERE r.referral_at >= '2025-10-01' AND r.referral_at < '2026-10-01'
  AND r.referral_type <> 'Duplicate';
