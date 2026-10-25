-- Every 2026 operational movement with both quantities (as recorded, and converted to vials) and its
-- accounting postings. One row per (event, posting); events with no posting appear once with blanks. SYNTHETIC.
SELECT t.inventory_event_key, t.site_key, t.therapy_key, t.event_at, t.event_type, t.unit_type,
       t.qty AS recorded_qty,
       CASE WHEN t.unit_type = 'CARTON' THEN t.qty * th.vials_per_carton ELSE t.qty END AS qty_vials,
       g.gl_line_key, g.posting_date, g.entry_type, g.qty_vials AS posted_vials
FROM inventory_transactions t
JOIN therapies th ON th.therapy_key = t.therapy_key
LEFT JOIN accounting_ledger g ON g.source_event_key = t.inventory_event_key
WHERE t.event_at >= '2026-01-01'
ORDER BY t.inventory_event_key, g.posting_date, g.gl_line_key;
