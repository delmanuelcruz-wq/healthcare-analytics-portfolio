-- T-104 Orders currently in Prior Authorization, aged from the stage start to the snapshot (SYNTHETIC).
-- One row per order; the open (latest) authorization request is shown when there is one.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date'),
pa AS (
    SELECT o.order_key, o.patient_key, o.therapy_key, o.site_key, o.stage_updated_at AS entered_stage_at,
           CAST(julianday((SELECT d FROM as_of)) - julianday(date(o.stage_updated_at)) AS INTEGER) AS days_in_stage
    FROM orders o
    WHERE o.stage = 'Prior Authorization'
)
SELECT pa.*,
       CASE WHEN days_in_stage > 30 THEN '31+ days' WHEN days_in_stage > 14 THEN '15-30 days'
            WHEN days_in_stage > 7 THEN '8-14 days' ELSE '0-7 days' END AS aging_bucket,
       a.auth_key AS latest_request, a.requested_at, a.as_of_status AS request_status, u.umbrella_name AS payer_at_request
FROM pa
LEFT JOIN authorizations a ON a.auth_key = (SELECT x.auth_key FROM authorizations x WHERE x.order_key = pa.order_key
                                            ORDER BY x.requested_at DESC, x.auth_key DESC LIMIT 1)
LEFT JOIN payer_umbrella_map m ON m.plan_key = a.plan_key_at_request
LEFT JOIN payer_umbrellas u ON u.umbrella_key = m.umbrella_key
ORDER BY days_in_stage DESC, pa.order_key;
