-- Boundary checks for the seven-quarter trend (SQLite). Parameter :therapy.
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
-- 1) visits that would land in a different quarter if bucketed on UTC instead of site-local time
-- 2) treated visits in the in-progress quarter (2026-Q4, through the Oct 24 snapshot) - excluded from the trend
WITH treated AS (
    SELECT DISTINCT a.appt_key, a.start_local, a.start_utc
    FROM appointments a
    JOIN administrations ad ON ad.appt_key = a.appt_key AND ad.therapy_key = :therapy AND ad.administered_flag = 1
    WHERE a.status = 'Complete' AND a.meds_administered = 1
)
SELECT
    (SELECT COUNT(*) FROM treated t
       JOIN calendar cl ON cl.cal_date = date(t.start_local)
       JOIN calendar cu ON cu.cal_date = date(t.start_utc)
      WHERE cl.quarter <> cu.quarter AND cl.quarter BETWEEN '2025-Q1' AND '2026-Q3')  AS quarter_shift_if_utc,
    (SELECT COUNT(*) FROM treated WHERE start_local >= '2026-10-01')                   AS partial_q4_visits,
    (SELECT MAX(start_local) FROM treated)                                              AS last_treated_visit;
