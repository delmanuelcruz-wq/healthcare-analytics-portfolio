# Issue ticket - delivery explore: lineage fields blank for refill deliveries

> SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance. Fictional BI model, fictional pharmacy feed, synthetic data. Roles only, no names.

| | |
|---|---|
| **Type** | BI model defect (join) + source data-quality items |
| **Priority** | High - therapy, patient, order and visit fields blank on 71% of delivery rows |
| **Raised by** | Analyst (reporting) |
| **For** | BI platform team (sections 1-6); pharmacy-feed owner (section 7) |
| **Status** | Drafted with evidence; fix proposed, not applied to any production model |

## 1. Summary
In the delivery explore, therapy, patient, order, pharmacy, fill and visit fields are blank on 317 of 446 delivery rows. The source tables have the values. The blanks come from the explore's join, which only matches **original** fills. Refill deliveries never join.

## 2. Steps to reproduce
1. Open the delivery explore and add *Ticket*, *Fill reference* and *Therapy*.
2. Filter *Fill reference* contains `-R`.
3. Every row shows a blank *Therapy*. Same result in SQL: [`sql/01_explore_as_modeled.sql`](sql/01_explore_as_modeled.sql).

## 3. Expected vs actual
| Field | Expected blank | Actual blank (as modeled) | After corrected join |
|---|---:|---:|---:|
| Therapy | ~0% | 71.1% (317) | 0.7% (3) |
| Patient | ~0% | 71.1% (317) | 0.7% (3) |
| Order | ~0% | 71.1% (317) | 0.7% (3) |
| Pharmacy | ~0% | 71.1% (317) | 0.7% (3) |
| Fill date | ~0% | 71.1% (317) | 0.7% (3) |
| Vials dispensed | ~0% | 71.1% (317) | 0.7% (3) |
| Visit date | ~0% | 71.1% (317) | 0.7% (3) |
| Destination site | ~0% | 0.0% (0) | 0.0% (0) |
| Shipped | ~0% | 0.0% (0) | 0.0% (0) |
| Delivered | ~0% | 1.6% (7) | 1.6% (7) |

## 4. Root cause (field lineage)
`Therapy` <- `prescriptions.therapy_key` <- join `delivery_tickets.fill_ref = prescriptions.rx_key`.
The pharmacy feed types an original fill as `RX####` and refill *n* as `RX####-R<n>`. A suffixed reference never equals a bare `rx_key`, so every refill row loses every field that comes through that join. The fill and visit fields were also joined to fill 0 only, so even matched rows pointed at the original fill.

## 5. Proposed model fix
Parse `fill_ref` into `rx_key` + `fill_number`, join **`rx_fills` on both**, then join prescriptions and the appointment through the fill ([`sql/03_corrected.sql`](sql/03_corrected.sql)).
Validation: 446 rows for 446 tickets (1:1). Remaining blanks are listed in section 7 and are source issues, not model issues.

## 6. Why not the quick fix
Matching with `LIKE rx_key || '%'` and joining fills on `rx_key` alone removes the blanks by attaching every fill of the prescription to every ticket: **1329 rows for 446 tickets** (3.0x). Visit dates and vials become wrong for most rows ([`sql/02_quick_fix.sql`](sql/02_quick_fix.sql)).

## 7. Source data-quality items (for the pharmacy-feed owner)
9 rows: Fill reference resolves to no fill: 3, Shipped to a different site than the visit: 2, Delivered without a delivered time: 4. Not issues: 3 tickets still in transit at the snapshot have a blank delivered time, as they should.

| Issue | Ticket | Fill reference | Detail |
|---|---|---|---|
| Fill reference resolves to no fill | DT00089 | `RXO073-R1` | Typed reference matches no prescription fill even after parsing |
| Shipped to a different site than the visit | DT00100 | `RX0083` | Ticket site S05, visit site S03 |
| Fill reference resolves to no fill | DT00211 | `RXO114-R1` | Typed reference matches no prescription fill even after parsing |
| Delivered without a delivered time | DT00278 | `RX0048-R2` | Status Delivered, timestamp blank in the feed |
| Shipped to a different site than the visit | DT00294 | `RX0127-R2` | Ticket site S04, visit site S05 |
| Fill reference resolves to no fill | DT00314 | `RX0086-2R` | Typed reference matches no prescription fill even after parsing |
| Delivered without a delivered time | DT00328 | `RX0115-R1` | Status Delivered, timestamp blank in the feed |
| Delivered without a delivered time | DT00334 | `RX0077-R2` | Status Delivered, timestamp blank in the feed |
| Delivered without a delivered time | DT00376 | `RX0174` | Status Delivered, timestamp blank in the feed |

## 8. Impact and ask
- Any delivery report using this explore undercounts refill shipments by therapy, site and patient.
- The blank share is about the same in every full month, July to October (69%-73%), so this is a modeling gap from the start, not a recent break.
- Ask: apply the join in section 5 to the explore, expose `fill_number` as a dimension, and route section 7 to the feed owner.
