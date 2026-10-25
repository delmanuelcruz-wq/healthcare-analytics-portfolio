-- T-101 "How many patients do we have at Saltmeadow?" - three honest answers, one agreed (SYNTHETIC).
WITH as_of AS (SELECT value AS cutoff, date(value) AS d FROM meta WHERE key = 'as_of_cutoff')
SELECT 'Active now (agreed): treated at S01 in the last 90 days or booked at S01' AS definition,
       COUNT(DISTINCT patient_key) AS patients
FROM appointments, as_of
WHERE site_key = 'S01'
  AND ((status = 'Complete' AND meds_administered = 1 AND date(start_local) > date(as_of.d, '-90 days') AND start_local <= as_of.cutoff)
       OR (status IN ('Scheduled', 'Confirmed') AND start_local > as_of.cutoff))
UNION ALL
SELECT 'Ever treated at S01', COUNT(DISTINCT patient_key)
FROM appointments WHERE site_key = 'S01' AND status = 'Complete' AND meds_administered = 1
UNION ALL
SELECT 'Ever assigned to S01 at intake (any state)', COUNT(*)
FROM patients WHERE primary_site_key = 'S01';
