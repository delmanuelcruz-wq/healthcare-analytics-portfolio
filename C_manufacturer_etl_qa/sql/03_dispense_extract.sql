-- Dispense extract: one row per treated appointment x program therapy in the reporting weeks.
-- injection_ordinal and first_therapy_date are computed over the patient's FULL history for
-- that therapy - a week-only extract would label every returning patient as dose #1.
SELECT w.week_start, v.program_key, v.therapy_key, v.appt_key, v.patient_key, v.order_key, v.site_key,
       date(v.start_local)                                                         AS treatment_date,
       v.vials, v.lines,
       (SELECT COUNT(*) FROM program_visits h
         WHERE h.patient_key = v.patient_key AND h.therapy_key = v.therapy_key
           AND h.start_local <= v.start_local)                                     AS injection_ordinal,
       (SELECT date(MIN(h.start_local)) FROM program_visits h
         WHERE h.patient_key = v.patient_key AND h.therapy_key = v.therapy_key)    AS first_therapy_date,
       vs.payer_segment
FROM program_visits v
JOIN weeks w ON v.start_local >= w.week_start AND v.start_local < w.week_end
JOIN visit_segment vs ON vs.appt_key = v.appt_key
ORDER BY w.week_start, v.program_key, v.appt_key, v.therapy_key;
