-- Target tables for the incremental refresh demo (SQLite, in memory).
-- SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.

-- Every status change ever received. The natural key (appt_key, changed_at) makes re-deliveries and
-- overlapping windows harmless: INSERT OR IGNORE keeps the first copy.
CREATE TABLE appt_change_history (
    appt_key    TEXT NOT NULL,
    changed_at  TEXT NOT NULL,
    change_type TEXT NOT NULL,
    new_status  TEXT NOT NULL,
    site_key    TEXT,
    start_local TEXT NOT NULL,
    load_seq    INTEGER NOT NULL,          -- the load that first delivered the row
    PRIMARY KEY (appt_key, changed_at)
);

-- Current state: one row per appointment. Upsert rule: a row replaces the current one only if its
-- changed_at is newer, so a late or out-of-order file can never move an appointment backwards.
CREATE TABLE appt_current (
    appt_key    TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    changed_at  TEXT NOT NULL,
    site_key    TEXT,
    start_local TEXT NOT NULL,
    load_seq    INTEGER NOT NULL
);

-- One row per delivery, including re-deliveries and files that changed nothing.
CREATE TABLE load_audit (
    load_seq              INTEGER PRIMARY KEY,
    file_name             TEXT NOT NULL,
    file_date             TEXT,
    arrived_at            TEXT NOT NULL,   -- simulated delivery time (deterministic, not wall-clock)
    sha256_12             TEXT,
    rows_in_file          INTEGER NOT NULL,
    rows_inserted         INTEGER NOT NULL,
    duplicates_ignored    INTEGER NOT NULL,
    appts_new             INTEGER NOT NULL,
    appts_updated         INTEGER NOT NULL,
    stale_rows_skipped    INTEGER NOT NULL,
    late_updates          INTEGER NOT NULL, -- inserted outcome rows recorded 3+ days after the visit
    restates_closed_month INTEGER NOT NULL, -- inserted rows for visits in a month that had already closed
    max_changed_at        TEXT,
    note                  TEXT
);

CREATE INDEX ix_history_load ON appt_change_history(load_seq);

CREATE TEMP TABLE stage (
    appt_key TEXT, changed_at TEXT, change_type TEXT, new_status TEXT, site_key TEXT, start_local TEXT
);
CREATE INDEX temp.ix_stage ON stage(appt_key, changed_at);
