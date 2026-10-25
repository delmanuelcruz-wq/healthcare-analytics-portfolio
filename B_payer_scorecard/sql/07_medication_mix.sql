-- Therapy mix by quarter. The ranking measure is distinct treated VISITS per therapy; line
-- items and distinct patients are shown so nobody mistakes one for another.
SELECT q.quarter, ad.therapy_key, t.therapy_label,
       COUNT(DISTINCT qv.appt_key)      AS treated_visits,
       COUNT(DISTINCT qv.patient_key)   AS patients,
       COUNT(ad.admin_key)              AS line_items,
       SUM(ad.vials)                    AS vials
FROM quarters q
JOIN qualifying_visits qv ON qv.start_local >= q.q_start AND qv.start_local < q.q_end
JOIN administrations ad ON ad.appt_key = qv.appt_key AND ad.administered_flag = 1
JOIN therapies t ON t.therapy_key = ad.therapy_key
GROUP BY q.quarter, ad.therapy_key
ORDER BY q.quarter, treated_visits DESC;
