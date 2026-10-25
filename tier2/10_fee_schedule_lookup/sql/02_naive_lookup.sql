-- The tempting shortcut: a VLOOKUP-style lookup on the code alone (first schedule row for the code),
-- with a blank-or-zero result read as "not found". Shown only to quantify what it gets wrong.
-- SYNTHETIC DEMONSTRATION - every amount is invented.
WITH first_row AS (
    SELECT mock_code, fee_row_key, fictional_fee_amount, claim_type, effective_from, effective_to,
           ROW_NUMBER() OVER (PARTITION BY mock_code ORDER BY fee_row_key) AS rn
    FROM mock_fee_schedule
)
SELECT r.request_key, r.mock_code, r.claim_type_requested, r.service_date,
       f.fee_row_key AS naive_fee_row, f.claim_type AS naive_claim_type,
       f.effective_from AS naive_effective_from, f.effective_to AS naive_effective_to,
       f.fictional_fee_amount AS naive_amount_synthetic,
       CASE WHEN f.fee_row_key IS NULL OR f.fictional_fee_amount = 0 THEN 'Not found' ELSE 'Priced' END AS naive_result
FROM lookup_requests r
LEFT JOIN first_row f ON f.mock_code = r.mock_code AND f.rn = 1
ORDER BY r.request_key;
