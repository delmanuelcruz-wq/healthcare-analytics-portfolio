-- Idempotent load of whatever sits in temp.stage. Parameters :load_seq, :file_month (first day of the file's month).
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.
-- Run inside one transaction per file. Statement order matters: measure, insert history, upsert current.

-- 1. Latest change per appointment in this file, classified against the current state BEFORE the upsert.
DROP TABLE IF EXISTS temp.stage_latest;
CREATE TEMP TABLE stage_latest AS
SELECT s.*,
       CASE WHEN c.appt_key IS NULL THEN 'new'
            WHEN s.changed_at > c.changed_at THEN 'updated'
            WHEN s.changed_at < c.changed_at THEN 'stale'
            ELSE 'same' END AS outcome
FROM stage s
LEFT JOIN appt_current c ON c.appt_key = s.appt_key
WHERE s.changed_at = (SELECT MAX(t.changed_at) FROM stage t WHERE t.appt_key = s.appt_key);

-- 2. History: natural key (appt_key, changed_at). Re-delivered and overlapping rows are ignored.
INSERT OR IGNORE INTO appt_change_history (appt_key, changed_at, change_type, new_status, site_key, start_local, load_seq)
SELECT appt_key, changed_at, change_type, new_status, site_key, start_local, :load_seq FROM stage;

-- 3. Current state: newer wins, older never overwrites.
INSERT INTO appt_current (appt_key, status, changed_at, site_key, start_local, load_seq)
SELECT appt_key, new_status, changed_at, site_key, start_local, :load_seq FROM stage_latest WHERE true
ON CONFLICT (appt_key) DO UPDATE SET
    status = excluded.status, changed_at = excluded.changed_at, site_key = excluded.site_key,
    start_local = excluded.start_local, load_seq = excluded.load_seq
WHERE excluded.changed_at > appt_current.changed_at;

-- 4. Measures for the audit row.
SELECT (SELECT COUNT(*) FROM stage)                                                          AS rows_in_file,
       (SELECT COUNT(*) FROM appt_change_history WHERE load_seq = :load_seq)                  AS rows_inserted,
       (SELECT COUNT(*) FROM stage_latest WHERE outcome = 'new')                              AS appts_new,
       (SELECT COUNT(*) FROM stage_latest WHERE outcome = 'updated')                          AS appts_updated,
       (SELECT COUNT(*) FROM stage_latest WHERE outcome = 'stale')                            AS stale_rows_skipped,
       (SELECT COUNT(*) FROM appt_change_history WHERE load_seq = :load_seq
          AND new_status IN ('Complete', 'No Show', 'Cancelled')
          AND julianday(date(changed_at)) - julianday(date(start_local)) >= 3)                AS late_updates,
       (SELECT COUNT(*) FROM appt_change_history WHERE load_seq = :load_seq
          AND start_local < :file_month)                                                      AS restates_closed_month,
       (SELECT MAX(changed_at) FROM stage)                                                    AS max_changed_at;
