-- Booked treatment pipeline after the snapshot, by week. This is what is on the
-- schedule today - not a forecast (most later visits simply are not booked yet).
SELECT c.week_start,
       COUNT(DISTINCT a.appt_key)                               AS booked_visits,
       COUNT(DISTINCT CASE WHEN a.status = 'Confirmed' THEN a.appt_key END) AS confirmed_visits,
       COUNT(DISTINCT a.patient_key)                            AS booked_patients
FROM appointments a
JOIN calendar c ON c.cal_date = date(a.start_local)
WHERE a.start_local > (SELECT value FROM meta WHERE key = 'as_of_cutoff')
  AND a.status IN ('Scheduled', 'Confirmed')
GROUP BY c.week_start
ORDER BY c.week_start;
