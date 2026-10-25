# Recruiter summary - Project B

**Ten-payer quarterly scorecard** · SQLite · Python · Excel (openpyxl, live formulas) · Plotly · synthetic data

**What it is:** A Q2 vs Q3 scorecard for ten fictional payer umbrellas. It covers referrals, prior-authorization approval, patients served,
business-day time to chair, and therapy mix.

**Why it is interesting:** It shows a first draft and the reviewed rebuild side by side, with each correction measured:

- Using order dates overstated new business by 48%.
- Following decisions instead of the request cohort moved individual payers' approval rates by up to 7 points.
- Current-insurance attribution would mislabel 1 in 4 new patients.
- A date-only `BETWEEN` silently dropped every request on the last day of the quarter.

**Craft:** Insurance-at-event joins over effective-dated intervals, half-open quarters, alias grouping before distinct counts,
an Excel `NETWORKDAYS` cross-check, a cohort maturity triangle, 10 tests and a 12-check QA log.

**Honest scope:** On the job I built a substantial draft that needed a definition rebuild. This portfolio version is an independent
reconstruction on fabricated data, not an approved report.
