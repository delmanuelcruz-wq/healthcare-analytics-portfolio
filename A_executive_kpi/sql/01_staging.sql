-- Project A staging layer (SQLite). Temp tables so every KPI reads one agreed definition.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.

-- A treated visit = appointment marked Complete, medication administered, and at least
-- one administration line actually given. Cancelled visits with stray lines and
-- "completed but drug held" visits are excluded by construction.
DROP TABLE IF EXISTS temp.qualifying_visits;
CREATE TEMP TABLE qualifying_visits AS
SELECT a.appt_key, a.patient_key, a.order_key, a.site_key, a.therapy_key, a.start_local,
       substr(a.start_local, 1, 7) || '-01' AS month_start
FROM appointments a
WHERE a.status = 'Complete'
  AND a.meds_administered = 1
  AND EXISTS (SELECT 1 FROM administrations ad
              WHERE ad.appt_key = a.appt_key AND ad.administered_flag = 1);
CREATE INDEX temp.ix_qv_patient ON qualifying_visits(patient_key, start_local);

-- First treatment derived from events, not from the system's first-appointment flag.
DROP TABLE IF EXISTS temp.first_treatment;
CREATE TEMP TABLE first_treatment AS
SELECT patient_key, MIN(start_local) AS first_treated_at,
       substr(MIN(start_local), 1, 7) || '-01' AS month_start
FROM qualifying_visits
GROUP BY patient_key;

-- One row per provider record with a stable person-level id (duplicates share a
-- source identity) and the provider's own county via the primary ZIP crosswalk row.
DROP TABLE IF EXISTS temp.provider_identity;
CREATE TEMP TABLE provider_identity AS
SELECT p.provider_key,
       MIN(p.provider_key) OVER (PARTITION BY p.source_identity_key) AS provider_id,
       p.source_identity_key, p.fictional_practice, p.primary_specialty, s.specialty_label,
       x.county_key, c.county_name, c.state_code, p.created_date
FROM providers p
JOIN specialties s ON s.specialty_code = p.primary_specialty
LEFT JOIN postal_county_crosswalk x ON x.zip5 = p.practice_zip5 AND x.is_primary = 1
LEFT JOIN counties c ON c.county_key = x.county_key;

DROP TABLE IF EXISTS temp.provider_referrals;
CREATE TEMP TABLE provider_referrals AS
SELECT pi.provider_id, r.referral_key, r.patient_key, date(r.referral_at) AS ref_date, r.referral_type
FROM referrals r
JOIN provider_identity pi ON pi.provider_key = r.provider_key;
CREATE INDEX temp.ix_pr ON provider_referrals(provider_id, ref_date);

-- Provider people (deduplicated): attributes come from the earliest record.
DROP TABLE IF EXISTS temp.provider_people;
CREATE TEMP TABLE provider_people AS
SELECT pi.provider_id, pi.fictional_practice, pi.primary_specialty, pi.specialty_label,
       pi.county_key, pi.county_name, pi.state_code,
       (SELECT MIN(created_date) FROM provider_identity q WHERE q.provider_id = pi.provider_id) AS created_date,
       (SELECT COUNT(*) FROM provider_identity q WHERE q.provider_id = pi.provider_id) AS record_count
FROM provider_identity pi
WHERE pi.provider_key = pi.provider_id;
