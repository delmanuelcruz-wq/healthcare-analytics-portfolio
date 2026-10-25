-- Patient-level journey milestones for new patients created in Q2 2026
-- (old enough by the Oct 24 snapshot to have had a fair chance to start).
-- Python aggregates these into the funnel and median lead times.
SELECT p.patient_key,
       p.created_at,
       (SELECT MIN(o.created_at) FROM orders o WHERE o.patient_key = p.patient_key)          AS first_order_at,
       (SELECT MIN(e.event_at) FROM order_status_events e JOIN orders o USING (order_key)
         WHERE o.patient_key = p.patient_key AND e.new_stage = 'Ready to Schedule')         AS ready_to_schedule_at,
       (SELECT MIN(a.booked_at) FROM appointments a WHERE a.patient_key = p.patient_key)     AS first_booking_at,
       ft.first_treated_at
FROM patients p
LEFT JOIN first_treatment ft ON ft.patient_key = p.patient_key
WHERE p.created_at >= '2026-04-01' AND p.created_at < '2026-07-01'
ORDER BY p.patient_key;
