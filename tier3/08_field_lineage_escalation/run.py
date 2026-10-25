"""Tier 3 #08 - BI field-lineage escalation (SYNTHETIC).

    python tier3/08_field_lineage_escalation/run.py

Runs the delivery explore three ways (as modeled, quick fix, corrected), audits null coverage
for every field users rely on, separates model-caused blanks from real source gaps, and writes
the escalation ticket (ISSUE_TICKET.md) with the evidence.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

SQL, OUT, CHARTS = HERE / "sql", HERE / "outputs", HERE / "charts"
FIELDS = [("therapy_key", "Therapy"), ("patient_key", "Patient"), ("order_key", "Order"), ("dispensing_pharmacy", "Pharmacy"),
          ("fill_date", "Fill date"), ("vials_dispensed", "Vials dispensed"), ("visit_at", "Visit date"),
          ("site_key", "Destination site"), ("shipped_at", "Shipped"), ("delivered_at", "Delivered")]


def load(con):
    return {v: P.query(con, SQL / f) for v, f in [("as_modeled", "01_explore_as_modeled.sql"),
                                                  ("quick_fix", "02_quick_fix.sql"), ("corrected", "03_corrected.sql")]}


def null_coverage(runs):
    out = []
    for col, label in FIELDS:
        row = dict(field=label, column=col)
        for v in ("as_modeled", "corrected"):
            n = sum(1 for r in runs[v] if r[col] is None)
            row[f"{v}_nulls"], row[f"{v}_null_pct"] = n, round(n / len(runs[v]), 4)
        out.append(row)
    return out


def residuals(runs):
    """What is still blank or wrong after the model fix - these are source problems, not model problems."""
    c = runs["corrected"]
    items = []
    for r in c:
        if r["rx_key"] is None:
            items.append(dict(issue="Fill reference resolves to no fill", ticket_key=r["ticket_key"], fill_ref=r["fill_ref"],
                              detail="Typed reference matches no prescription fill even after parsing", owner="Pharmacy feed"))
        if r["delivery_status"] == "Delivered" and r["delivered_at"] is None:
            items.append(dict(issue="Delivered without a delivered time", ticket_key=r["ticket_key"], fill_ref=r["fill_ref"],
                              detail="Status Delivered, timestamp blank in the feed", owner="Pharmacy feed"))
        if r["visit_site_key"] and r["visit_site_key"] != r["site_key"]:
            items.append(dict(issue="Shipped to a different site than the visit", ticket_key=r["ticket_key"],
                              fill_ref=r["fill_ref"], detail=f"Ticket site {r['site_key']}, visit site {r['visit_site_key']}",
                              owner="Pharmacy feed / site"))
    legit = [r["ticket_key"] for r in c if r["delivery_status"] == "In transit"]
    return items, legit


def null_by_month(runs):
    m = defaultdict(lambda: [0, 0])
    for r in runs["as_modeled"]:
        k = r["shipped_at"][:7]
        m[k][0] += 1
        m[k][1] += r["therapy_key"] is None
    return [dict(month=k, tickets=v[0], therapy_blank=v[1], blank_pct=round(v[1] / v[0], 4)) for k, v in sorted(m.items())]


def chart(cov):
    plt = P.mpl()
    CHARTS.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    labels = [r["field"] for r in cov][::-1]
    before = [r["as_modeled_null_pct"] * 100 for r in cov][::-1]
    after = [r["corrected_null_pct"] * 100 for r in cov][::-1]
    y = range(len(labels))
    ax.barh([i + 0.2 for i in y], before, height=0.38, color="#eb6834", label="As modeled")
    ax.barh([i - 0.2 for i in y], after, height=0.38, color="#2a78d6", label="Corrected join")
    for i, (b, a) in enumerate(zip(before, after)):
        ax.text(b + 0.8, i + 0.2, f"{b:.1f}%", va="center", fontsize=8.5, color="#52514e")
        ax.text(a + 0.8, i - 0.2, f"{a:.1f}%", va="center", fontsize=8.5, color="#52514e")
    ax.set_yticks(list(y), labels)
    ax.set_xlim(0, 100)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Blank fields in the delivery explore: the join, not the source", loc="left", fontsize=13,
                 fontweight="bold", color="#0b0b0b", pad=24)
    ax.text(0, 1.02, "Share of delivery rows with a null value, per field. Remaining blanks after the fix are real source gaps.",
            transform=ax.transAxes, fontsize=9.5, color="#52514e")
    fig.text(0.01, 0.01, P.DISCLAIMER + " | Coralline Infusion Network (fictional)", fontsize=7.5, color="#6f6d68")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CHARTS / "null_coverage.png", dpi=160, facecolor="#fcfcfb")
    plt.close(fig)


def write_ticket(runs, cov, items, legit, months):
    n = len(runs["as_modeled"])
    therapy = next(r for r in cov if r["column"] == "therapy_key")
    fan_rows, fan_tickets = len(runs["quick_fix"]), len({r["ticket_key"] for r in runs["quick_fix"]})
    kinds = Counter(i["issue"] for i in items)
    lines = [
        "# Issue ticket - delivery explore: lineage fields blank for refill deliveries", "",
        f"> {P.DISCLAIMER}. Fictional BI model, fictional pharmacy feed, synthetic data. Roles only, no names.", "",
        "| | |", "|---|---|",
        "| **Type** | BI model defect (join) + source data-quality items |",
        f"| **Priority** | High - therapy, patient, order and visit fields blank on {therapy['as_modeled_null_pct']:.0%} of delivery rows |",
        "| **Raised by** | Analyst (reporting) |",
        "| **For** | BI platform team (sections 1-6); pharmacy-feed owner (section 7) |",
        "| **Status** | Drafted with evidence; fix proposed, not applied to any production model |", "",
        "## 1. Summary",
        f"In the delivery explore, therapy, patient, order, pharmacy, fill and visit fields are blank on {therapy['as_modeled_nulls']} "
        f"of {n} delivery rows. The source tables have the values. The blanks come from the explore's join, which only matches "
        "**original** fills. Refill deliveries never join.", "",
        "## 2. Steps to reproduce",
        "1. Open the delivery explore and add *Ticket*, *Fill reference* and *Therapy*.",
        "2. Filter *Fill reference* contains `-R`.",
        "3. Every row shows a blank *Therapy*. Same result in SQL: [`sql/01_explore_as_modeled.sql`](sql/01_explore_as_modeled.sql).", "",
        "## 3. Expected vs actual",
        "| Field | Expected blank | Actual blank (as modeled) | After corrected join |", "|---|---:|---:|---:|"]
    for r in cov:
        lines.append(f"| {r['field']} | ~0% | {r['as_modeled_null_pct']:.1%} ({r['as_modeled_nulls']}) | "
                     f"{r['corrected_null_pct']:.1%} ({r['corrected_nulls']}) |")
    lines += ["", "## 4. Root cause (field lineage)",
              "`Therapy` <- `prescriptions.therapy_key` <- join `delivery_tickets.fill_ref = prescriptions.rx_key`.",
              "The pharmacy feed types an original fill as `RX####` and refill *n* as `RX####-R<n>`. A suffixed reference never "
              "equals a bare `rx_key`, so every refill row loses every field that comes through that join. The fill and visit "
              "fields were also joined to fill 0 only, so even matched rows pointed at the original fill.", "",
              "## 5. Proposed model fix",
              "Parse `fill_ref` into `rx_key` + `fill_number`, join **`rx_fills` on both**, then join prescriptions and the "
              "appointment through the fill ([`sql/03_corrected.sql`](sql/03_corrected.sql)).",
              f"Validation: {len(runs['corrected'])} rows for {n} tickets (1:1). Remaining blanks are listed in section 7 and are "
              "source issues, not model issues.", "",
              "## 6. Why not the quick fix",
              f"Matching with `LIKE rx_key || '%'` and joining fills on `rx_key` alone removes the blanks by attaching every fill "
              f"of the prescription to every ticket: **{fan_rows} rows for {fan_tickets} tickets** "
              f"({fan_rows / fan_tickets:.1f}x). Visit dates and vials become wrong for most rows ([`sql/02_quick_fix.sql`](sql/02_quick_fix.sql)).", "",
              "## 7. Source data-quality items (for the pharmacy-feed owner)",
              f"{len(items)} rows: " + ", ".join(f"{k}: {v}" for k, v in kinds.items()) +
              f". Not issues: {len(legit)} tickets still in transit at the snapshot have a blank delivered time, as they should.", "",
              "| Issue | Ticket | Fill reference | Detail |", "|---|---|---|---|"]
    lines += [f"| {i['issue']} | {i['ticket_key']} | `{i['fill_ref']}` | {i['detail']} |" for i in items]
    lines += ["", "## 8. Impact and ask",
              "- Any delivery report using this explore undercounts refill shipments by therapy, site and patient.",
              f"- The blank share is about the same in every full month, July to October "
              f"({min(m['blank_pct'] for m in months if m['tickets'] >= 20):.0%}-{max(m['blank_pct'] for m in months if m['tickets'] >= 20):.0%}), "
              "so this is a modeling gap from the start, not a recent break.",
              "- Ask: apply the join in section 5 to the explore, expose `fill_number` as a dimension, and route section 7 to the feed owner.", ""]
    (HERE / "ISSUE_TICKET.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    con = P.connect()
    runs = load(con)
    cov = null_coverage(runs)
    items, legit = residuals(runs)
    months = null_by_month(runs)
    counts = [dict(version=v, rows=len(r), distinct_tickets=len({x["ticket_key"] for x in r})) for v, r in runs.items()]
    for name, rows in [("null_coverage", cov), ("source_issues", items), ("row_counts", counts), ("as_modeled_blank_by_month", months)]:
        P.write_csv(rows, OUT / f"{name}.csv")
    chart(cov)
    write_ticket(runs, cov, items, legit, months)
    print(f"#08 built: {counts[0]['rows']} tickets; therapy blank {cov[0]['as_modeled_null_pct']:.1%} -> "
          f"{cov[0]['corrected_null_pct']:.1%}; {len(items)} source issues -> ISSUE_TICKET.md")


if __name__ == "__main__":
    main()
