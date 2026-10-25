"""Tier 3 #07 - Ad hoc service-desk tickets with SQL answers and a response log (SYNTHETIC).

    python tier3/07_service_desk_tickets/run.py

Reads five fictional tickets from tickets.csv, runs each ticket's SQL against the warehouse,
writes the answer files to ./outputs and builds RESPONSE_LOG.md (question, clarification,
agreed definition, answer, caveats, turnaround).
"""
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

OUT = HERE / "outputs"
REPLIED_AT = {"T-101": "2026-10-19 11:05", "T-102": "2026-10-20 16:10", "T-103": "2026-10-21 13:20",
              "T-104": "2026-10-22 15:45", "T-105": "2026-10-26 09:30"}     # simulated, for the turnaround column
CAVEATS = {
    "T-101": "'Patients at a site' has three defensible meanings; the reply leads with the agreed one and labels the others.",
    "T-102": "A schedule changes hourly; the list is as of the Oct 24 snapshot. Keys only - the coordinator looks up details in the source system.",
    "T-103": "One license appears twice in the register; the duplicate is excluded so the same gap is not chased twice.",
    "T-104": "Stage age starts when the order entered Prior Authorization, not when the order was created.",
    "T-105": "Each visit sits in a gap between two coverage intervals - likely a data-entry gap to confirm with billing, not proof the patient was uninsured.",
}


def load_tickets():
    with (HERE / "tickets.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def answer(con, ticket):
    return P.query(con, HERE / ticket["sql_file"])


def summarize(tid, rows):
    if tid == "T-101":
        return (f"{rows[0]['patients']} active patients at S01 (agreed definition). For context: {rows[1]['patients']} were ever "
                f"treated there and {rows[2]['patients']} were assigned to the site at intake.")
    if tid == "T-102":
        st = Counter(r["booking_status"] for r in rows)
        return (f"{len(rows)} booked visits on {len({r['visit_date'] for r in rows})} days: {st['Confirmed']} confirmed, "
                f"{st['Scheduled']} not yet confirmed.")
    if tid == "T-103":
        g = Counter(r["gap"].startswith("Register says") for r in rows)
        soon = min(rows, key=lambda r: r["expiry_date"])
        days = (datetime.fromisoformat(soon["expiry_date"]) - datetime(2026, 10, 24)).days
        return (f"{len(rows)} license records lack a document: {g[False]} where the register shows none, {g[True]} where the "
                f"register says on file but the document library is empty. Flagged first: {soon['license_record_key']} "
                f"also expires in {days} days.")
    if tid == "T-104":
        old = [r for r in rows if r["days_in_stage"] > 30]
        buckets = Counter(r["aging_bucket"] for r in rows)
        order = ["0-7 days", "8-14 days", "15-30 days", "31+ days"]
        return (f"{len(rows)} orders are in Prior Authorization; {len(old)} have been there more than 30 days "
                f"({', '.join(f'{r['order_key']} {r['days_in_stage']}d' for r in old)}). Aging: "
                + ", ".join(f"{b} {buckets.get(b, 0)}" for b in order) + ".")
    if tid == "T-105":
        return (f"{len(rows)} treated visits had no coverage interval on the visit date ("
                + ", ".join(r["appt_key"] for r in rows) + ").")
    raise KeyError(tid)


def turnaround(received, replied):
    hours = (datetime.fromisoformat(replied) - datetime.fromisoformat(received)).total_seconds() / 3600
    return f"{hours:.1f} h" if hours < 24 else f"{hours / 24:.1f} days (weekend)"


def write_log(log):
    lines = ["# Response log - fictional service-desk tickets", "",
             f"> {P.DISCLAIMER}. Requesters are roles, not people. Answers come from the synthetic warehouse (snapshot 2026-10-24).",
             "> Received and replied times are simulated to show the turnaround column.", ""]
    for r in log:
        lines += [f"## {r['ticket_id']} - {r['requester_role']}", "",
                  "| | |", "|---|---|",
                  f"| **Asked** | \"{r['request_as_written']}\" |",
                  f"| **Clarifying question** | {r['clarifying_question']} |",
                  f"| **Agreed definition** | {r['agreed_definition']} |",
                  f"| **Answer** | {r['answer']} |",
                  f"| **Rows delivered** | {r['rows']} - [`outputs/{r['output_file']}`](outputs/{r['output_file']}) · SQL: [`{r['sql_file']}`]({r['sql_file']}) |",
                  f"| **Caveat sent with it** | {r['caveat']} |",
                  f"| **Received / replied** | {r['received_at']} / {r['replied_at']} ({r['turnaround']}) |", ""]
    (HERE / "RESPONSE_LOG.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    con = P.connect()
    log = []
    for t in load_tickets():
        rows = answer(con, t)
        out = f"{t['ticket_id'].replace('-', '')}_answer.csv"
        P.write_csv(rows, OUT / out)
        log.append(dict(t, answer=summarize(t["ticket_id"], rows), rows=len(rows), output_file=out,
                        caveat=CAVEATS[t["ticket_id"]], replied_at=REPLIED_AT[t["ticket_id"]],
                        turnaround=turnaround(t["received_at"], REPLIED_AT[t["ticket_id"]])))
    P.write_csv([{k: r[k] for k in ("ticket_id", "requester_role", "received_at", "replied_at", "turnaround", "rows", "answer")}
                 for r in log], OUT / "response_log.csv")
    write_log(log)
    print(f"#07 built: {len(log)} tickets answered -> RESPONSE_LOG.md")


if __name__ == "__main__":
    main()
