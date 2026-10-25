-- The REJECTED first draft: approval rate from decisions dated in the quarter, whatever
-- quarter the request came from. Also shows how duplicate decision rows inflate raw counts.
WITH finals AS (
    SELECT d.decision_key, d.auth_key, d.decision_at, d.decision_result,
           COALESCE((SELECT pd.umbrella_key FROM plan_dim pd WHERE pd.plan_key = a.plan_key_at_request), 'NO_COVERAGE') AS umbrella_key,
           a.requested_at
    FROM authorization_decisions d JOIN authorizations a USING (auth_key)
    WHERE d.decision_result IN ('Approved', 'Denied')
)
SELECT q.quarter, f.umbrella_key,
       COUNT(*)                                                                    AS decision_rows,
       COUNT(DISTINCT f.auth_key)                                                  AS decided_requests,
       SUM(CASE WHEN f.decision_result = 'Approved' THEN 1 ELSE 0 END)             AS approved_rows,
       COUNT(DISTINCT CASE WHEN f.decision_result = 'Approved' THEN f.auth_key END) AS approved,
       COUNT(DISTINCT CASE WHEN f.decision_result = 'Denied' THEN f.auth_key END)   AS denied,
       COUNT(DISTINCT CASE WHEN f.requested_at < q.q_start THEN f.auth_key END)     AS decided_from_earlier_quarters
FROM quarters q
JOIN finals f ON f.decision_at >= q.q_start AND f.decision_at < q.q_end
GROUP BY q.quarter, f.umbrella_key;
