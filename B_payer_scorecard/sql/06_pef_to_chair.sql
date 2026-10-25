-- PEF-to-chair: business days from order series creation to the order's first treated visit.
-- Scope: new-patient and new-therapy orders (renewals are scheduled to a due date, which
-- would distort an access metric). Cohort = orders whose first treatment fell in Q2/Q3 2026.
-- networkdays_inclusive matches Excel NETWORKDAYS(start, end): weekdays, both endpoints counted.
WITH first_tx AS (
    SELECT order_key, MIN(start_local) AS first_treated_at FROM qualifying_visits GROUP BY order_key
)
SELECT op.order_key, op.patient_key, op.order_type, op.therapy_key, op.umbrella_at_order AS umbrella_key,
       op.created_at, f.first_treated_at,
       CASE WHEN f.first_treated_at >= '2026-07-01' THEN 'Q3 2026' ELSE 'Q2 2026' END                AS treated_quarter,
       CASE WHEN cs.cal_date <= ce.cal_date
            THEN ce.weekday_seq - cs.weekday_seq + cs.is_weekday            -- Excel: NETWORKDAYS(start, end)
            ELSE -(cs.weekday_seq - ce.weekday_seq + ce.is_weekday) END                               AS networkdays_inclusive,
       CAST(julianday(date(f.first_treated_at)) - julianday(date(op.created_at)) AS INTEGER)         AS calendar_days
FROM order_payer op
JOIN first_tx f USING (order_key)
JOIN calendar cs ON cs.cal_date = date(op.created_at)
JOIN calendar ce ON ce.cal_date = date(f.first_treated_at)
WHERE op.order_type IN ('New patient', 'New therapy')
  AND f.first_treated_at >= '2026-04-01' AND f.first_treated_at < '2026-10-01'
ORDER BY op.order_key;
