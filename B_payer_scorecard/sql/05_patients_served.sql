-- Unique patients served (1+ treated visit) in a window, attributed to the payer covering
-- their MOST RECENT treated visit in that window. Counted after grouping plans to umbrellas.
WITH windows(window_label, w_start, w_end) AS (
    VALUES ('T12M to Sep 30, 2026', '2025-10-01', '2026-10-01'),
           ('T12M to Sep 30, 2025', '2024-10-01', '2025-10-01'),
           ('Q2 2026', '2026-04-01', '2026-07-01'),
           ('Q3 2026', '2026-07-01', '2026-10-01')
),
ranked AS (
    SELECT w.window_label, vp.patient_key, vp.umbrella_key,
           ROW_NUMBER() OVER (PARTITION BY w.window_label, vp.patient_key ORDER BY vp.start_local DESC) AS rn
    FROM windows w JOIN visit_payer vp ON vp.start_local >= w.w_start AND vp.start_local < w.w_end
)
SELECT r.window_label, u.umbrella_key, u.umbrella_name, u.sort_order, COUNT(DISTINCT r.patient_key) AS patients_served
FROM umbrella_order u
LEFT JOIN ranked r ON r.umbrella_key = u.umbrella_key AND r.rn = 1
WHERE r.window_label IS NOT NULL
GROUP BY r.window_label, u.umbrella_key
ORDER BY r.window_label, u.sort_order;
