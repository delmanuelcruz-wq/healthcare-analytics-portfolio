# Recruiter summary - Project A

**Referral-to-treatment executive KPIs** · SQLite · Python · Plotly · synthetic healthcare data

**What it is:** A leadership dashboard for a fictional multi-site infusion provider. It tracks new referred patients,
first treatment starts, completed visits, the booked schedule, and referral sources that are active or going quiet.

**Why it is interesting:** Each headline number has a tempting wrong version, and the project shows both:

- Order series ran 46% above new patients, because renewals are not new business.
- A first-appointment flag shortcut missed 12.3% of real treatment starts.
- Counting medication line items overstated visits by about 9%.

**How it is built:** One reproducible synthetic data model (standard-library Python, fixed seed). Seven SQL files. A 15-check
QA suite. 14 unit tests, including an independent Python re-implementation of the rolling-90-day provider logic.

**Honest scope:** On the job I built two draft BI trend reports and helped define the provider rules. Everything else
here was built independently on fabricated data. It is not a production system.
