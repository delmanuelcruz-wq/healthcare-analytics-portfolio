-- Opening position at the Dec 31, 2025 close, computed independently in each system. SYNTHETIC.
-- Operational: first weekly snapshot's opening count + every movement before 2026 (cartons converted to vials).
-- Accounting: the OPENING_BALANCE line. The two must agree before any 2026 difference can be explained.
WITH first_snap AS (
    SELECT site_key, therapy_key, beginning_qty,
           ROW_NUMBER() OVER (PARTITION BY site_key, therapy_key ORDER BY week_start) AS rn
    FROM inventory_snapshots
),
moves AS (
    SELECT t.site_key, t.therapy_key,
           SUM(CASE WHEN t.unit_type = 'CARTON' THEN t.qty * th.vials_per_carton ELSE t.qty END) AS qty
    FROM inventory_transactions t JOIN therapies th ON th.therapy_key = t.therapy_key
    WHERE t.event_at < '2026-01-01'
    GROUP BY 1, 2
)
SELECT s.site_key, s.therapy_key, s.beginning_qty + COALESCE(m.qty, 0) AS ops_opening_vials,
       (SELECT SUM(g.qty_vials) FROM accounting_ledger g WHERE g.site_key = s.site_key AND g.therapy_key = s.therapy_key
          AND g.entry_type = 'OPENING_BALANCE') AS gl_opening_vials,
       (SELECT MAX(g.fictional_unit_cost) FROM accounting_ledger g WHERE g.therapy_key = s.therapy_key) AS fictional_unit_cost
FROM first_snap s
LEFT JOIN moves m ON m.site_key = s.site_key AND m.therapy_key = s.therapy_key
WHERE s.rn = 1
ORDER BY s.site_key, s.therapy_key;
