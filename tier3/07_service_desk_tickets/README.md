# Tier 3 #07 - Ad hoc request desk: five tickets, five definitions

> **SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.**
> The tickets, requesters (roles only) and data are fictional (seed `20261024`). Short micro-case, written as a postmortem.

**Read:** [`RESPONSE_LOG.md`](RESPONSE_LOG.md) - each ticket as asked, the clarifying question, the agreed definition, the answer, the caveat and the turnaround.

## Situation

Ad hoc requests arrive in plain language from people who do not think in tables: a sales leader, a site coordinator,
a compliance coordinator, an intake manager and a billing lead. Each request sounds simple, and each hides a definition
choice that changes the number.

## The five tickets

| Ticket | As asked | The hidden choice | Answer (synthetic) |
|---|---|---|---|
| T-101 | "How many patients do we have at Saltmeadow?" | Assigned at intake vs ever treated vs active now | **123** active (also 322 ever treated, 430 ever assigned) |
| T-102 | "Next week's schedule for Heronmouth?" | Which week; booked statuses only; keys, never patient details | 12 booked visits, 9 not yet confirmed |
| T-103 | "Which nurses are missing license documents?" | Include "flag says on file but library is empty"; skip duplicate entries | 4 records; one also expires in 10 days |
| T-104 | "Orders stuck in prior authorization for 30+ days?" | Age from entering the stage, not from order creation | 3 of 58 orders (66, 39, 33 days) plus aging buckets |
| T-105 | "Treated visits with no insurance on file?" | Coverage on the **visit date**, not today | 4 visits, each in a gap between two coverage intervals |

## What went wrong (the trap)

Answering the literal question fast would have produced confident but wrong numbers:
- 430 "patients at Saltmeadow" when the leader meant active patients.
- Two missing documents instead of four.
- Order age measured from creation, which flags 5 orders instead of 3, including two that only entered prior authorization recently.

## What I did

1. Asked one short clarifying question per ticket, offering the choices in the requester's words.
2. Wrote the agreed definition into the log *before* writing SQL ([`tickets.csv`](tickets.csv)).
3. Answered with one SQL file per ticket ([`sql/`](sql/)) and one CSV per answer ([`outputs/`](outputs/)).
4. Sent each answer with a caveat. Example: "a coverage gap is likely a data-entry gap to confirm, not proof the patient was uninsured."

## Evidence

- `python tier3/07_service_desk_tickets/run.py` rebuilds every answer and the response log.
- [`tests/test_t07_tickets.py`](tests/test_t07_tickets.py) has 7 tests:
  - T-103 and T-105 return exactly the gaps planted in the ground-truth register.
  - T-104's stage ages are recomputed in Python.
  - T-102 contains only booked S04 visits in the requested week.
  - No answer file carries a personal-detail column.

## Lessons

- The clarifying question is the work. Offering two or three concrete options gets a fast, unambiguous reply.
- Lead with the agreed number, and show the alternatives labelled so nobody re-derives them later.
- Keys, not people: a schedule request is answered with appointment and patient keys. The requester looks up details in the source system.

## Real vs built

| | |
|---|---|
| **On-the-job exposure (general terms)** | Handled multiple guided ad hoc requests for patient, scheduling, document and order reports. |
| **Built here** | Five fictional tickets, their SQL, the response log and the tests, on synthetic data. No real requests or requesters are described. |
