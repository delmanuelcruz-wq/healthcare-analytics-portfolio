-- The tempting quick fix: match the prescription with LIKE and join fills on rx_key alone. SYNTHETIC.
-- It fills the blanks - by attaching EVERY fill of the prescription to every ticket, so rows fan out
-- and visit dates, vials and fill dates are wrong for most rows.
SELECT t.ticket_key, t.fill_ref, t.site_key, t.shipped_at, t.delivery_status, t.delivered_at,
       p.rx_key, p.therapy_key, p.patient_key, p.order_key, p.dispensing_pharmacy,
       f.fill_number, f.fill_date, f.vials_dispensed, a.start_local AS visit_at, a.site_key AS visit_site_key
FROM delivery_tickets t
LEFT JOIN prescriptions p ON t.fill_ref LIKE p.rx_key || '%'
LEFT JOIN rx_fills f ON f.rx_key = p.rx_key
LEFT JOIN appointments a ON a.appt_key = f.for_appt_key
ORDER BY t.ticket_key, f.fill_number;
