-- T-105 Treated visits with no insurance interval covering the visit date (SYNTHETIC).
SELECT a.appt_key, a.patient_key, date(a.start_local) AS visit_date, a.site_key, a.therapy_key,
       (SELECT MAX(c.effective_to) FROM payer_history c WHERE c.patient_key = a.patient_key
          AND c.effective_to < date(a.start_local)) AS previous_coverage_ended,
       (SELECT MIN(c.effective_from) FROM payer_history c WHERE c.patient_key = a.patient_key
          AND c.effective_from > date(a.start_local)) AS next_coverage_starts
FROM appointments a
WHERE a.status = 'Complete' AND a.meds_administered = 1
  AND NOT EXISTS (SELECT 1 FROM payer_history c WHERE c.patient_key = a.patient_key
                  AND c.effective_from <= date(a.start_local)
                  AND (c.effective_to IS NULL OR c.effective_to >= date(a.start_local)))
ORDER BY visit_date;
