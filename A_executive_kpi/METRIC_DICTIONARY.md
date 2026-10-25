# Metric dictionary - Project A

> SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.

| Metric | Grain counted | Exact rule (SQLite) | Edge cases handled | Source |
|---|---|---|---|---|
| New referred patients | patient | `COUNT(DISTINCT patient_key)` where `created_at` in month | Partial month labelled | `02_monthly_kpis.sql` |
| Referral events | referral event | `COUNT(*)` of referrals in month | Includes renewals, new-therapy referrals and duplicate faxes - shown for contrast only | `02_monthly_kpis.sql` |
| New order series | order series | `COUNT(DISTINCT order_key)` by `orders.created_at` | Measures therapy orders, not new patients | `02_monthly_kpis.sql` |
| Qualifying (treated) visit | appointment | `status = 'Complete' AND meds_administered = 1 AND EXISTS (administration line with administered_flag = 1)` | Excludes held-medication visits, prepared-but-wasted lines, and lines charted on cancelled visits | `01_staging.sql` |
| New treatment starts | patient | Month of `MIN(start_local)` over each patient's qualifying visits | Stale or duplicated first-appointment flags ignored; local time, not UTC | `01_staging.sql`, `02_monthly_kpis.sql` |
| New treatment starts (flag method) | patient | `first_patient_appt_flag = 1 AND status = 'Complete' AND meds_administered = 1` | Kept only to show the gap | `02_monthly_kpis.sql` |
| Completed treatment visits | appointment | `COUNT(DISTINCT appt_key)` over qualifying visits | Split lots, add-on lines and duplicate lines do not multiply | `02_monthly_kpis.sql` |
| Administration line items | line item | `COUNT(*)` of administrations by visit month | Shown to quantify overstatement | `02_monthly_kpis.sql` |
| Booked visits | appointment | `start_local > as_of cutoff AND status IN ('Scheduled','Confirmed')` | Pipeline, not forecast | `03_future_bookings.sql` |
| Provider person | provider identity | `MIN(provider_key) OVER (PARTITION BY source_identity_key)` | 3 duplicate records merged | `01_staging.sql` |
| Active provider | provider person | `>= 1` referral with `ref_date` in `(as_of - 90 days, as_of]` | Only referrals `<= as_of` are visible | `04`, `05` |
| Newly active provider | provider person | Active, and first ever referral inside the window | Subset of active | `04` |
| Dormant provider | provider person | First referral `<= as_of`, zero referrals in the window | Never-referred excluded | `04`, `05` |
| Never-referred provider | provider person | Record created `<= as_of`, no referral `<= as_of` | Not dormant | `04`, `05` |
| Provider county | provider person | Practice ZIP joined to `postal_county_crosswalk` with `is_primary = 1` | ZIP 00150 straddles two counties | `01_staging.sql` |
| Specialty | provider person | `providers.primary_specialty` | 20 providers hold a second specialty; the bridge table is not joined | `06_county_specialty.sql` |
| Q2 2026 cohort funnel | patient | Patients created Apr 1 - Jun 30, 2026; milestones from orders, status events, appointments, first treatment | Medians ignore negative or missing durations | `07_cohort_milestones.sql`, `run.py` |

**Reporting month** = calendar month of the site-local timestamp. **Snapshot** = Oct 24, 2026 23:59:59 local.
