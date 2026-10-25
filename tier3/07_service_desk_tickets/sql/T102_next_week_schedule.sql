-- T-102 Next week's booked schedule at S04 (Mon Oct 26 - Fri Oct 30, 2026). Keys only, no patient details (SYNTHETIC).
SELECT date(a.start_local) AS visit_date, time(a.start_local) AS start_time, a.appt_key, a.patient_key,
       a.therapy_key, t.therapy_label, a.status AS booking_status
FROM appointments a
JOIN therapies t ON t.therapy_key = a.therapy_key
WHERE a.site_key = 'S04'
  AND a.start_local >= '2026-10-26' AND a.start_local < '2026-10-31'
  AND a.status IN ('Scheduled', 'Confirmed')
ORDER BY a.start_local, a.appt_key;
