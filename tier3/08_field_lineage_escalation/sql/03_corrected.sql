-- Corrected model: parse the pharmacy's fill reference into (rx_key, fill_number), then join the FILL,
-- not the prescription. One row per ticket, every lineage field reachable. SYNTHETIC.
--   "RX0012"    -> rx_key RX0012, fill_number 0 (original fill)
--   "RX0012-R3" -> rx_key RX0012, fill_number 3 (third refill)
WITH parsed AS (
    SELECT t.*,
           CASE WHEN instr(upper(trim(t.fill_ref)), '-R') > 0
                THEN substr(upper(trim(t.fill_ref)), 1, instr(upper(trim(t.fill_ref)), '-R') - 1)
                ELSE upper(trim(t.fill_ref)) END AS parsed_rx_key,
           CASE WHEN instr(upper(trim(t.fill_ref)), '-R') > 0
                THEN CAST(substr(upper(trim(t.fill_ref)), instr(upper(trim(t.fill_ref)), '-R') + 2) AS INTEGER)
                ELSE 0 END AS parsed_fill_number
    FROM delivery_tickets t
)
SELECT t.ticket_key, t.fill_ref, t.site_key, t.shipped_at, t.delivery_status, t.delivered_at,
       p.rx_key, p.therapy_key, p.patient_key, p.order_key, p.dispensing_pharmacy,
       f.fill_number, f.fill_date, f.vials_dispensed, a.start_local AS visit_at, a.site_key AS visit_site_key
FROM parsed t
LEFT JOIN rx_fills f ON f.rx_key = t.parsed_rx_key AND f.fill_number = t.parsed_fill_number
LEFT JOIN prescriptions p ON p.rx_key = f.rx_key
LEFT JOIN appointments a ON a.appt_key = f.for_appt_key
ORDER BY t.ticket_key;
