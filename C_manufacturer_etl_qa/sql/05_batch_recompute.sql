-- For every logged submission batch, recompute what the operator's process WOULD have produced
-- at generation time (same rules the original process used), plus a "now" recount for dispense
-- files so late-arriving updates (restatement candidates) are visible.
SELECT s.*,
       CASE s.file_type
         WHEN 'DISPENSE' THEN (SELECT COUNT(*) FROM program_lines l
                               WHERE l.program_key = s.program_key AND l.administered_flag = 1
                                 AND l.start_local >= s.reporting_week_start AND l.start_local < date(s.reporting_week_start, '+7 days')
                                 AND l.updated_at <= s.generated_at)
         WHEN 'INVENTORY' THEN (SELECT COUNT(*) FROM inventory_transactions t JOIN program_therapy pt USING (therapy_key)
                                WHERE pt.program_key = s.program_key
                                  AND date(t.event_at) >= s.reporting_week_start AND date(t.event_at) < date(s.reporting_week_start, '+7 days'))
         WHEN 'STATUS' THEN (SELECT COUNT(*) FROM order_status_events e JOIN orders o USING (order_key)
                             JOIN program_therapy pt ON pt.therapy_key = o.therapy_key
                             WHERE pt.program_key = s.program_key
                               AND date(e.event_at) >= s.reporting_week_start AND date(e.event_at) < date(s.reporting_week_start, '+7 days')
                               AND e.event_at <= s.generated_at)
       END AS recomputed_source,
       CASE s.file_type
         WHEN 'DISPENSE' THEN (SELECT COUNT(DISTINCT l.appt_key || '|' || l.therapy_key) FROM program_lines l
                               WHERE l.program_key = s.program_key AND l.administered_flag = 1
                                 AND l.start_local >= s.reporting_week_start AND l.start_local < date(s.reporting_week_start, '+7 days')
                                 AND l.updated_at <= s.generated_at)
         WHEN 'INVENTORY' THEN (SELECT COUNT(*) FROM inventory_snapshots i JOIN program_therapy pt USING (therapy_key)
                                WHERE pt.program_key = s.program_key AND i.week_start = s.reporting_week_start)
         WHEN 'STATUS' THEN (SELECT COUNT(DISTINCT e.order_key || '|' || e.new_stage || '|' || date(e.event_at))
                             FROM order_status_events e JOIN orders o USING (order_key)
                             JOIN program_therapy pt ON pt.therapy_key = o.therapy_key
                             WHERE pt.program_key = s.program_key
                               AND date(e.event_at) >= s.reporting_week_start AND date(e.event_at) < date(s.reporting_week_start, '+7 days')
                               AND e.event_at <= s.generated_at)
       END AS recomputed_output,
       CASE WHEN s.file_type = 'DISPENSE' THEN
            (SELECT COUNT(DISTINCT l.appt_key || '|' || l.therapy_key) FROM program_lines l
             WHERE l.program_key = s.program_key AND l.administered_flag = 1
               AND l.start_local >= s.reporting_week_start AND l.start_local < date(s.reporting_week_start, '+7 days'))
       END AS recomputed_output_now
FROM submission_log s
ORDER BY s.reporting_week_start, s.program_key, s.file_type;
