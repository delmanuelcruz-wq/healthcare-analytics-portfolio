-- The "Pharmacy deliveries" explore as it was modeled (fictional BI model, rebuilt in SQLite). SYNTHETIC.
-- Lineage of the fields users said were blank: therapy, patient, order, pharmacy, fill and visit fields all
-- come through ONE join: delivery_tickets.fill_ref = prescriptions.rx_key. That only works for original fills -
-- the pharmacy types refills as "RX####-R<n>", which never equals a bare rx_key.
SELECT t.ticket_key, t.fill_ref, t.site_key, t.shipped_at, t.delivery_status, t.delivered_at,
       p.rx_key, p.therapy_key, p.patient_key, p.order_key, p.dispensing_pharmacy,
       f.fill_number, f.fill_date, f.vials_dispensed, a.start_local AS visit_at, a.site_key AS visit_site_key
FROM delivery_tickets t
LEFT JOIN prescriptions p ON p.rx_key = t.fill_ref
LEFT JOIN rx_fills f ON f.rx_key = p.rx_key AND f.fill_number = 0
LEFT JOIN appointments a ON a.appt_key = f.for_appt_key
ORDER BY t.ticket_key;
