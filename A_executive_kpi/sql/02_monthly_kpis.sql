-- Monthly executive KPIs, Jan 2025 - Oct 2026 (October 2026 is partial: data as of Oct 24).
-- Each column is a separately defined measure; several "wrong but tempting" versions
-- are kept side by side so the dashboard can show why the definitions matter.
WITH RECURSIVE months(month_start) AS (
    SELECT '2025-01-01'
    UNION ALL
    SELECT date(month_start, '+1 month') FROM months WHERE month_start < '2026-10-01'
),
new_patients AS (      -- business-wide new referral proxy: patient record created
    SELECT substr(created_at, 1, 7) || '-01' AS m, COUNT(DISTINCT patient_key) AS n FROM patients GROUP BY 1
),
referral_events AS (   -- every referral event, including renewals and duplicate faxes
    SELECT substr(referral_at, 1, 7) || '-01' AS m, COUNT(*) AS n FROM referrals GROUP BY 1
),
new_orders AS (        -- order series created: measures therapy orders, not new patients
    SELECT substr(created_at, 1, 7) || '-01' AS m, COUNT(DISTINCT order_key) AS n FROM orders GROUP BY 1
),
starts_derived AS (    -- month of each patient's first treated visit
    SELECT month_start AS m, COUNT(DISTINCT patient_key) AS n FROM first_treatment GROUP BY 1
),
starts_flag AS (       -- the quick Looker-style version: first-appt flag + Complete + administered
    SELECT substr(start_local, 1, 7) || '-01' AS m, COUNT(DISTINCT patient_key) AS n
    FROM appointments
    WHERE first_patient_appt_flag = 1 AND status = 'Complete' AND meds_administered = 1
    GROUP BY 1
),
treated_visits AS (    -- distinct treated appointments
    SELECT month_start AS m, COUNT(DISTINCT appt_key) AS n FROM qualifying_visits GROUP BY 1
),
line_items AS (        -- what you get by counting administration line IDs
    SELECT substr(a.start_local, 1, 7) || '-01' AS m, COUNT(*) AS n
    FROM administrations ad JOIN appointments a USING (appt_key) GROUP BY 1
),
complete_status AS (   -- status = Complete regardless of whether medication was given
    SELECT substr(start_local, 1, 7) || '-01' AS m, COUNT(*) AS n
    FROM appointments WHERE status = 'Complete' GROUP BY 1
)
SELECT mo.month_start,
       CASE WHEN mo.month_start = substr((SELECT value FROM meta WHERE key = 'as_of_date'), 1, 7) || '-01'
            THEN 1 ELSE 0 END                                        AS is_partial_month,
       COALESCE(np.n, 0)  AS new_referred_patients,
       COALESCE(re.n, 0)  AS referral_events,
       COALESCE(no.n, 0)  AS new_order_series,
       COALESCE(sd.n, 0)  AS new_treatment_starts,
       COALESCE(sf.n, 0)  AS new_treatment_starts_flag_method,
       COALESCE(tv.n, 0)  AS completed_treatment_visits,
       COALESCE(li.n, 0)  AS administration_line_items,
       COALESCE(cs.n, 0)  AS complete_status_appointments
FROM months mo
LEFT JOIN new_patients np    ON np.m = mo.month_start
LEFT JOIN referral_events re ON re.m = mo.month_start
LEFT JOIN new_orders no      ON no.m = mo.month_start
LEFT JOIN starts_derived sd  ON sd.m = mo.month_start
LEFT JOIN starts_flag sf     ON sf.m = mo.month_start
LEFT JOIN treated_visits tv  ON tv.m = mo.month_start
LEFT JOIN line_items li      ON li.m = mo.month_start
LEFT JOIN complete_status cs ON cs.m = mo.month_start
ORDER BY mo.month_start;
