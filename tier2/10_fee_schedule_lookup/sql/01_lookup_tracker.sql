-- Fee-schedule lookup tracker (SQLite). One row per lookup request, exactly one bucket each.
-- SYNTHETIC DEMONSTRATION - every amount is invented and must never be read as reimbursement.
--
-- A MATCH needs all three: same code, same claim type, and a service date inside the row's effective
-- interval [effective_from, effective_to] (blank effective_to = open-ended). Buckets are assigned in order:
--   1 Duplicate request   - same code + claim type + service date as an earlier request (the original keeps its bucket)
--   2 Matched / Zero-pay  - a match exists; $0.00 is a real rate (non-covered), not "no match"
--   3 No match            - the code is not on the fee schedule at all
--   4 Wrong claim type    - the code is on the schedule, but only under another claim type
--   5 Out of date range   - code and claim type exist, but no interval covers the service date
WITH req AS (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY r.mock_code, r.claim_type_requested, r.service_date
                                   ORDER BY r.request_key) AS dup_rank,
           FIRST_VALUE(r.request_key) OVER (PARTITION BY r.mock_code, r.claim_type_requested, r.service_date
                                            ORDER BY r.request_key) AS original_request
    FROM lookup_requests r
),
matched AS (
    SELECT r.request_key, f.fee_row_key, f.fictional_fee_amount, f.effective_from, f.effective_to, f.pricing_note
    FROM req r
    JOIN mock_fee_schedule f ON f.mock_code = r.mock_code AND f.claim_type = r.claim_type_requested
     AND r.service_date >= f.effective_from AND (f.effective_to IS NULL OR r.service_date <= f.effective_to)
),
on_schedule AS (
    SELECT mock_code, GROUP_CONCAT(DISTINCT claim_type) AS claim_types, MIN(effective_from) AS earliest_from
    FROM mock_fee_schedule GROUP BY mock_code
)
SELECT r.request_key, r.batch_key, r.mock_code, r.claim_type_requested, r.service_date,
       CASE
         WHEN r.dup_rank > 1 THEN 'Duplicate request'
         WHEN m.fee_row_key IS NOT NULL AND m.fictional_fee_amount = 0 THEN 'Zero-pay ($0.00)'
         WHEN m.fee_row_key IS NOT NULL THEN 'Matched'
         WHEN s.mock_code IS NULL THEN 'No match'
         WHEN NOT EXISTS (SELECT 1 FROM mock_fee_schedule f WHERE f.mock_code = r.mock_code
                          AND f.claim_type = r.claim_type_requested) THEN 'Wrong claim type'
         ELSE 'Out of date range'
       END AS bucket,
       CASE WHEN r.dup_rank > 1 THEN NULL ELSE m.fee_row_key END           AS matched_fee_row,
       CASE WHEN r.dup_rank > 1 THEN NULL ELSE m.fictional_fee_amount END  AS fictional_fee_amount_synthetic,
       CASE WHEN r.dup_rank > 1 THEN NULL ELSE m.effective_from END        AS effective_from,
       CASE WHEN r.dup_rank > 1 THEN NULL ELSE m.effective_to END          AS effective_to,
       s.claim_types                                                       AS claim_types_on_schedule,
       s.earliest_from                                                     AS earliest_effective_from,
       CASE WHEN r.dup_rank > 1 THEN r.original_request END                AS duplicate_of,
       (SELECT COUNT(*) FROM matched m2 WHERE m2.request_key = r.request_key) AS match_rows
FROM req r
LEFT JOIN matched m ON m.request_key = r.request_key
LEFT JOIN on_schedule s ON s.mock_code = r.mock_code
ORDER BY r.request_key;
