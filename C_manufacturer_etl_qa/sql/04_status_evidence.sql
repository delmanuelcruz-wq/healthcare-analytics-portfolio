-- Every order status event with the evidence the rules engine needs. "Archived" is never
-- read as "stopped": doses before the event and doses after archive are checked explicitly.
SELECT e.status_event_key, e.order_key, o.patient_key, o.therapy_key, pt.program_key,
       e.previous_stage, e.new_stage, e.event_at, e.reason, e.correction_flag,
       o.created_at AS order_created_at, o.archived_at, o.stage AS current_stage,
       (SELECT MIN(a.start_local) FROM appointments a
         WHERE a.order_key = e.order_key AND a.status = 'Complete' AND a.meds_administered = 1)        AS first_dose_at,
       (SELECT COUNT(*) FROM appointments a
         WHERE a.order_key = e.order_key AND a.status = 'Complete' AND a.meds_administered = 1
           AND a.start_local <= e.event_at)                                                           AS doses_before_event,
       (SELECT COUNT(*) FROM appointments a
         WHERE a.order_key = e.order_key AND a.status = 'Complete' AND a.meds_administered = 1
           AND o.archived_at IS NOT NULL AND a.start_local > o.archived_at)                           AS doses_after_archive,
       (SELECT COUNT(*) FROM order_status_events f
         WHERE f.order_key = e.order_key AND f.new_stage = e.new_stage AND f.event_at = e.event_at
           AND f.status_event_key < e.status_event_key)                                               AS earlier_identical_events
FROM order_status_events e
JOIN orders o USING (order_key)
LEFT JOIN program_therapy pt ON pt.therapy_key = o.therapy_key
ORDER BY e.event_at, e.status_event_key;
