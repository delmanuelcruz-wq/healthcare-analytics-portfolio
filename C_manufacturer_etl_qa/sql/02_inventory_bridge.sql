-- Weekly inventory bridge per site x program therapy:
--   opening + receipts + returns - administered - waste/expired +/- count adjustments = computed closing
-- compared with the system's closing count. Carton receipts are converted to vials first.
WITH tx AS (
    SELECT t.site_key, t.therapy_key, c.week_start, t.event_type, t.unit_type,
           CASE WHEN t.unit_type = 'CARTON' THEN t.qty * pt.vials_per_carton ELSE t.qty END AS qty_vials,
           t.qty AS qty_as_recorded
    FROM inventory_transactions t
    JOIN calendar c ON c.cal_date = date(t.event_at)
    JOIN program_therapy pt ON pt.therapy_key = t.therapy_key
)
SELECT s.snapshot_key, s.week_start, s.site_key, s.therapy_key, pt.program_key,
       s.beginning_qty                                                                       AS opening_qty,
       COALESCE(SUM(CASE WHEN tx.event_type = 'RECEIPT' THEN tx.qty_vials END), 0)            AS receipts,
       COALESCE(SUM(CASE WHEN tx.event_type = 'RETURN_IN' THEN tx.qty_vials END), 0)          AS returns_in,
       -COALESCE(SUM(CASE WHEN tx.event_type = 'ADMINISTERED' THEN tx.qty_vials END), 0)      AS administered,
       -COALESCE(SUM(CASE WHEN tx.event_type IN ('ADJ_WASTE', 'ADJ_EXPIRED') THEN tx.qty_vials END), 0) AS waste_expired,
       COALESCE(SUM(CASE WHEN tx.event_type = 'ADJ_COUNT' THEN tx.qty_vials END), 0)          AS count_adjustments,
       COALESCE(SUM(CASE WHEN tx.unit_type <> 'VIAL' THEN 1 ELSE 0 END), 0)                   AS carton_rows_converted,
       COALESCE(SUM(tx.qty_vials - tx.qty_as_recorded), 0)                                     AS conversion_effect,
       COUNT(tx.event_type)                                                                    AS transactions,
       s.ending_qty                                                                            AS system_closing_qty
FROM inventory_snapshots s
JOIN program_therapy pt ON pt.therapy_key = s.therapy_key
LEFT JOIN tx ON tx.site_key = s.site_key AND tx.therapy_key = s.therapy_key AND tx.week_start = s.week_start
WHERE s.week_start IN (SELECT week_start FROM weeks)
GROUP BY s.snapshot_key
ORDER BY s.week_start, pt.program_key, s.site_key, s.therapy_key;
