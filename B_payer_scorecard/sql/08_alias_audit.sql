-- Alias audit for the current T12M window: distinct patients per RAW PLAN vs per UMBRELLA.
-- Summing plan-level distinct counts double-counts patients who moved between plans of the
-- same umbrella (e.g. the three-brand plan family under PU08).
SELECT vp.plan_key, pd.raw_plan_name, vp.umbrella_key, COUNT(DISTINCT vp.patient_key) AS patients_served_plan
FROM visit_payer vp
JOIN plan_dim pd ON pd.plan_key = vp.plan_key
WHERE vp.start_local >= '2025-10-01' AND vp.start_local < '2026-10-01'
GROUP BY vp.plan_key
ORDER BY vp.umbrella_key, vp.plan_key;
