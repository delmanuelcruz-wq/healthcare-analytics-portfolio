-- New referred patients per quarter by payer umbrella AT INTAKE (insurance at the event),
-- with the two rejected alternatives kept for the revision log:
--   * order-series method (Order Series Created Date - measures therapy orders, not new patients)
--   * current-insurance attribution (re-labels history whenever a patient changes plans)
SELECT q.quarter, u.umbrella_key, u.umbrella_name, u.sort_order,
       (SELECT COUNT(DISTINCT pp.patient_key) FROM patient_payer pp
         WHERE pp.umbrella_at_intake = u.umbrella_key AND pp.created_at >= q.q_start AND pp.created_at < q.q_end) AS new_patients,
       (SELECT COUNT(DISTINCT pp.patient_key) FROM patient_payer pp
         WHERE pp.umbrella_current = u.umbrella_key AND pp.created_at >= q.q_start AND pp.created_at < q.q_end) AS new_patients_current_insurance,
       (SELECT COUNT(DISTINCT op.order_key) FROM order_payer op
         WHERE op.umbrella_at_order = u.umbrella_key AND op.created_at >= q.q_start AND op.created_at < q.q_end) AS order_series_created
FROM quarters q CROSS JOIN umbrella_order u
ORDER BY q.quarter, u.sort_order;
