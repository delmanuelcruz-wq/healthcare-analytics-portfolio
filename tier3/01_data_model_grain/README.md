# Tier 3 #01 - Data-model onboarding: a grain guide that cannot drift

> **SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.**
> Fictional infusion network, generated data (seed `20261024`). Short micro-case, written as a postmortem.

**Read:** [`GRAIN_GUIDE.md`](GRAIN_GUIDE.md) - the referral-to-treatment path, measured fan-out traps, an ERD of all 38
tables and every table's grain. It is generated from the schema by [`grain_guide.py`](grain_guide.py).

## Situation

Starting on a new healthcare data model means learning dozens of tables at once: patients, referrals, order series,
authorizations, appointments and medication lines. The questions come immediately ("how many new patients?", "how many
treatments?") and every answer depends on the **grain**: what one row means.

## The trap

The model is a chain of one-to-many relationships. Every join down the chain quietly multiplies rows, and the numbers
still look plausible. On the synthetic data:

| Shortcut | Inflation |
|---|---:|
| Counting patients after joining referrals | x1.54 |
| Counting "new patients" from order series | x1.51 |
| Joining payer coverage to visits without the effective date | x1.75 |
| Reading authorization outcomes from decision events | x1.17 |
| Counting treated visits after joining medication lines | x1.08 |
| Taking provider specialty through the bridge table | x1.08 |

A seventh trap is latent: one ZIP straddles two counties. No provider practices there yet, so a crosswalk join without
the primary-row filter looks correct today and breaks the day one does.

## What I did

1. Wrote down the grain and key of every table, then **checked** each key is unique. All 38 hold.
2. Built the ERD from the declared foreign keys (54 relationships), so the diagram is generated, not drawn.
3. Measured each trap on real joins: naive rows vs grain-safe rows, with the rule that fixes it.
4. Put it in one generated page, so the guide is rebuilt with the data and cannot go stale.

## Evidence

- `python tier3/01_data_model_grain/grain_guide.py` rebuilds [`GRAIN_GUIDE.md`](GRAIN_GUIDE.md), [`outputs/grain_checks.csv`](outputs/grain_checks.csv) and [`outputs/fanout_traps.csv`](outputs/fanout_traps.csv).
- [`tests/test_t01_grain.py`](tests/test_t01_grain.py) has 5 tests:
  - Every table holds its declared grain.
  - The ERD covers every foreign key.
  - Every trap inflates, and every safe join keeps the grain.
  - The payer join's 4-visit shortfall is exactly the coverage gaps planted in the ground-truth register.

## Lessons

- State the grain of the question first ("distinct patients", "distinct appointments"), then pick joins that keep it.
- `EXISTS` answers "has at least one"; `JOIN` answers "one row per match". Mixing them up is the most common inflation.
- Effective-dated tables (coverage, director assignments) always need the date condition. A gap or overlap is a data issue to report, not a reason to drop the condition.
- Documentation generated from the schema stays true; hand-drawn diagrams drift.

## Real vs built

| | |
|---|---|
| **On-the-job exposure (general terms)** | Hands-on onboarding to a healthcare data model and workflow mapping, with training. |
| **Built here** | The synthetic model itself, the generated grain guide and ERD, the measured traps and the tests. |
