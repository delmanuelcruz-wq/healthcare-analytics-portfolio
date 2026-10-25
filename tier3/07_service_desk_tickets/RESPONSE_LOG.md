# Response log - fictional service-desk tickets

> SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance. Requesters are roles, not people. Answers come from the synthetic warehouse (snapshot 2026-10-24).
> Received and replied times are simulated to show the turnaround column.

## T-101 - Sales leader

| | |
|---|---|
| **Asked** | "How many patients do we have at Saltmeadow?" |
| **Clarifying question** | Do you mean everyone ever assigned to the site, everyone ever treated there, or patients who are active now? |
| **Agreed definition** | Active patients at site S01: a treated visit at S01 in the last 90 days or a future booked visit at S01. Other two counts shown for context. |
| **Answer** | 123 active patients at S01 (agreed definition). For context: 322 were ever treated there and 430 were assigned to the site at intake. |
| **Rows delivered** | 3 - [`outputs/T101_answer.csv`](outputs/T101_answer.csv) · SQL: [`sql/T101_site_patients.sql`](sql/T101_site_patients.sql) |
| **Caveat sent with it** | 'Patients at a site' has three defensible meanings; the reply leads with the agreed one and labels the others. |
| **Received / replied** | 2026-10-19 09:12 / 2026-10-19 11:05 (1.9 h) |

## T-102 - Site coordinator

| | |
|---|---|
| **Asked** | "Can I get next week's schedule for Heronmouth?" |
| **Clarifying question** | Next week = Mon Oct 26 - Fri Oct 30? Booked visits only (Scheduled or Confirmed)? Patient keys only - no names leave the warehouse. |
| **Agreed definition** | Appointments at S04 starting Oct 26-30, 2026 with status Scheduled or Confirmed, by day and time, with therapy and confirmation status. |
| **Answer** | 12 booked visits on 5 days: 3 confirmed, 9 not yet confirmed. |
| **Rows delivered** | 12 - [`outputs/T102_answer.csv`](outputs/T102_answer.csv) · SQL: [`sql/T102_next_week_schedule.sql`](sql/T102_next_week_schedule.sql) |
| **Caveat sent with it** | A schedule changes hourly; the list is as of the Oct 24 snapshot. Keys only - the coordinator looks up details in the source system. |
| **Received / replied** | 2026-10-20 14:40 / 2026-10-20 16:10 (1.5 h) |

## T-103 - Compliance coordinator

| | |
|---|---|
| **Asked** | "Which nurses are missing license documents?" |
| **Clarifying question** | Should I include licenses where the register says a document is on file but the document library has nothing? And skip duplicate entries? |
| **Agreed definition** | License records with no document in the document index, or document_flag = 0, excluding duplicate records of the same license. |
| **Answer** | 4 license records lack a document: 2 where the register shows none, 2 where the register says on file but the document library is empty. Flagged first: LIC011 also expires in 10 days. |
| **Rows delivered** | 4 - [`outputs/T103_answer.csv`](outputs/T103_answer.csv) · SQL: [`sql/T103_missing_license_documents.sql`](sql/T103_missing_license_documents.sql) |
| **Caveat sent with it** | One license appears twice in the register; the duplicate is excluded so the same gap is not chased twice. |
| **Received / replied** | 2026-10-21 10:05 / 2026-10-21 13:20 (3.2 h) |

## T-104 - Intake manager

| | |
|---|---|
| **Asked** | "Which orders have been stuck in prior authorization for more than 30 days?" |
| **Clarifying question** | Stuck = the order's current stage is Prior Authorization and it entered that stage more than 30 days before the data snapshot (Oct 24)? |
| **Agreed definition** | Orders currently in Prior Authorization, aged from the stage start to the Oct 24 snapshot; list those over 30 days with their open request, and show the aging buckets for all. |
| **Answer** | 58 orders are in Prior Authorization; 3 have been there more than 30 days (OS03144 66d, OS03269 39d, OS03290 33d). Aging: 0-7 days 22, 8-14 days 18, 15-30 days 15, 31+ days 3. |
| **Rows delivered** | 58 - [`outputs/T104_answer.csv`](outputs/T104_answer.csv) · SQL: [`sql/T104_stuck_prior_auth.sql`](sql/T104_stuck_prior_auth.sql) |
| **Caveat sent with it** | Stage age starts when the order entered Prior Authorization, not when the order was created. |
| **Received / replied** | 2026-10-22 11:30 / 2026-10-22 15:45 (4.2 h) |

## T-105 - Billing lead

| | |
|---|---|
| **Asked** | "Can you find treated visits where we had no insurance on file?" |
| **Clarifying question** | No insurance on file on the visit date itself (not today)? Treated = Complete with medication given? |
| **Agreed definition** | Treated visits with no coverage interval covering the visit date for that patient. |
| **Answer** | 4 treated visits had no coverage interval on the visit date (AP001611, AP008342, AP009239, AP009651). |
| **Rows delivered** | 4 - [`outputs/T105_answer.csv`](outputs/T105_answer.csv) · SQL: [`sql/T105_visits_without_coverage.sql`](sql/T105_visits_without_coverage.sql) |
| **Caveat sent with it** | Each visit sits in a gap between two coverage intervals - likely a data-entry gap to confirm with billing, not proof the patient was uninsured. |
| **Received / replied** | 2026-10-23 16:20 / 2026-10-26 09:30 (2.7 days (weekend)) |
