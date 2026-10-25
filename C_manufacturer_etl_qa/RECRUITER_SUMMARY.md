# Recruiter summary - Project C

**Manufacturer data-agreement ETL and submission QA** · SQLite · Python · Plotly · synthetic data

**What it is:** A weekly reporting pipeline for two fictional manufacturer programs. It produces an inventory bridge, a
deduplicated dispense file with history-aware injection numbers, and a rules-checked status file. Each file has a control record
(count without header plus SHA-256). A console audits all 120 logged submissions.

**Highlights:**

- Recomputes every logged file at its generation time, and automatically diagnosed a wrong-week file and a duplicate-row file.
- Status rules engine: 18,897 events routed to Verified, Review or Escalate, with every planted exception caught and no false positives.
- Found the real bottleneck, timing. Building files on business day 5 instead of day 2-3 raises completeness from about 93% to 96%.
- Patient identifiers leave only as salted one-way tokens. Destinations are mock-only.

**Honest scope:** On the job this was guided, hands-on extract and QA-checklist work. Delivery and acceptance were not verified.
This is an independent reconstruction on fabricated data.
