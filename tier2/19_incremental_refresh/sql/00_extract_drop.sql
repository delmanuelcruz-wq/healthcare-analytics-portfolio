-- Source extract for one daily drop file (reads the attached warehouse as `wh`). Parameters :lo, :hi.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
-- Each drop carries every status change recorded in [:lo, :hi]. The window is two days wide on purpose
-- (yesterday + today), so a row missed by one file is picked up by the next. Overlap is handled by the load.
SELECT c.appt_key, c.changed_at, c.change_type, c.new_status, a.site_key, a.start_local
FROM wh.appointment_change_log c
JOIN wh.appointments a ON a.appt_key = c.appt_key
WHERE c.changed_at >= :lo AND c.changed_at <= :hi
ORDER BY c.changed_at, c.appt_key;
