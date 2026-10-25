-- Prior-authorization outcomes for the REQUEST cohort: requests submitted in the quarter,
-- outcome as of the snapshot. Pending requests are reported separately, never as denials.
-- Approval rate = approved / (approved + denied).
SELECT q.quarter, u.umbrella_key, u.umbrella_name, u.sort_order,
       COUNT(a.auth_key)                                          AS requests,
       COUNT(DISTINCT a.order_key)                                AS orders_requested,
       SUM(CASE WHEN a.request_sequence > 1 THEN 1 ELSE 0 END)    AS appeal_requests,
       SUM(CASE WHEN a.as_of_status = 'Approved' THEN 1 ELSE 0 END) AS approved,
       SUM(CASE WHEN a.as_of_status = 'Denied' THEN 1 ELSE 0 END)   AS denied,
       SUM(CASE WHEN a.as_of_status = 'Pending' THEN 1 ELSE 0 END)  AS pending
FROM quarters q
CROSS JOIN umbrella_order u
LEFT JOIN authorizations a
       ON a.requested_at >= q.q_start AND a.requested_at < q.q_end
      AND COALESCE((SELECT d.umbrella_key FROM plan_dim d WHERE d.plan_key = a.plan_key_at_request), 'NO_COVERAGE') = u.umbrella_key
GROUP BY q.quarter, u.umbrella_key
ORDER BY q.quarter, u.sort_order;
