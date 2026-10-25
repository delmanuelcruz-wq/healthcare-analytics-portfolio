"""Tier 3 #20 - Operational vs accounting inventory reconciliation (SYNTHETIC, learning case).

    python tier3/20_inventory_accounting_recon/run.py

At each 2026 month end (Jan-Sep), compares the operational inventory position (vials on hand per
the movement ledger) with the accounting position (general-ledger lines posted by that date), then
explains every vial of difference, event by event:

  Timing            - the event happened before month end, the posting landed after (reverses next month)
  Write-off not booked (real shortage) - vials physically gone, never written off in the books
  Receipt not invoiced - vials on the shelf, never booked
  Duplicate posting  - the books recorded one event twice
A naive comparison that skips the carton-to-vial conversion is shown alongside, because it invents a
shortage that is not there. Amounts use invented unit costs and are SYNTHETIC.
"""
import calendar
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

SQL, OUT, CHARTS = HERE / "sql", HERE / "outputs", HERE / "charts"
MONTH_ENDS = [date(2026, m, calendar.monthrange(2026, m)[1]) for m in range(1, 10)]
POSTING_SLA_DAYS = 14          # anything older with no posting is "not booked", not "not yet posted"
AS_OF = datetime(2026, 10, 24, 23, 59, 59)
CLASSES = ["Timing (posts next period)", "Write-off not booked (real shortage)", "Receipt not invoiced",
           "Duplicate posting in accounting", "Unexplained"]
WRITE_OFFS = {"ADJ_EXPIRED", "ADJ_COUNT", "ADJ_WASTE"}


def load(con):
    opening = P.query(con, SQL / "01_opening_positions.sql")
    events = {}
    for r in P.query(con, SQL / "02_events_and_postings.sql"):
        e = events.setdefault(r["inventory_event_key"], dict(
            key=r["inventory_event_key"], site=r["site_key"], therapy=r["therapy_key"], event_at=r["event_at"],
            event_type=r["event_type"], unit_type=r["unit_type"], recorded_qty=r["recorded_qty"], qty=r["qty_vials"],
            postings=[]))
        if r["gl_line_key"]:
            e["postings"].append((r["posting_date"], r["posted_vials"], r["gl_line_key"]))
    return opening, list(events.values())


def classify(e, me):
    """Explain one event's contribution to the month-end difference, or None if it contributes nothing."""
    end = me.isoformat() + " 23:59:59"
    if e["event_at"] > end:
        return None, 0
    posted = sum(q for d, q, _ in e["postings"] if d <= me.isoformat())
    residual = e["qty"] - posted
    if residual == 0:
        return None, 0
    if not e["postings"]:
        age = (AS_OF - datetime.fromisoformat(e["event_at"])).days
        if age <= POSTING_SLA_DAYS:
            return "Timing (posts next period)", residual
        if e["event_type"] == "RECEIPT":
            return "Receipt not invoiced", residual
        if e["event_type"] in WRITE_OFFS and e["qty"] < 0:
            return "Write-off not booked (real shortage)", residual
        return "Unexplained", residual
    if posted == 0:
        return "Timing (posts next period)", residual
    if len(e["postings"]) > 1 and all(q == e["qty"] for _, q, _ in e["postings"]):
        return "Duplicate posting in accounting", residual
    return "Unexplained", residual


def reconcile(opening, events):
    cost = {r["therapy_key"]: r["fictional_unit_cost"] for r in opening}
    cells = {(r["site_key"], r["therapy_key"]): r for r in opening}
    by_cell = defaultdict(list)
    for e in events:
        by_cell[(e["site"], e["therapy"])].append(e)
    recon, items = [], []
    for me in MONTH_ENDS:
        end = me.isoformat() + " 23:59:59"
        for cell, o in sorted(cells.items()):
            evs = [e for e in by_cell[cell] if e["event_at"] <= end]
            ops = o["ops_opening_vials"] + sum(e["qty"] for e in evs)
            naive = o["ops_opening_vials"] + sum(e["recorded_qty"] for e in evs)
            gl = o["gl_opening_vials"] + sum(q for e in by_cell[cell] for d, q, _ in e["postings"] if d <= me.isoformat())
            parts = dict.fromkeys(CLASSES, 0)
            for e in evs:
                cls, qty = classify(e, me)
                if cls:
                    parts[cls] += qty
                    items.append(dict(month_end=me.isoformat(), site_key=cell[0], therapy_key=cell[1], inventory_event_key=e["key"],
                                      event_type=e["event_type"], event_at=e["event_at"], qty_vials=e["qty"],
                                      first_posted=min((d for d, _, _ in e["postings"]), default=None),
                                      postings=len(e["postings"]), reconciling_vials=qty, classification=cls))
            row = dict(month_end=me.isoformat(), site_key=cell[0], therapy_key=cell[1], ops_vials=ops, gl_vials=gl,
                       difference_vials=ops - gl)
            row.update({k: v for k, v in zip(["timing_vials", "writeoff_not_booked_vials", "receipt_not_invoiced_vials",
                                              "duplicate_posting_vials", "unexplained_vials"], parts.values())})
            real = ops - gl - parts["Timing (posts next period)"]
            row.update(real_difference_vials=real, naive_ops_vials=naive, naive_difference_vials=naive - gl,
                       difference_value_synthetic=round((ops - gl) * cost[cell[1]], 2),
                       real_difference_value_synthetic=round(real * cost[cell[1]], 2))
            recon.append(row)
    return recon, items


def summarize(recon):
    out = []
    for me in MONTH_ENDS:
        rows = [r for r in recon if r["month_end"] == me.isoformat()]
        s = dict(month_end=me.isoformat())
        for k in ("difference_vials", "timing_vials", "writeoff_not_booked_vials", "receipt_not_invoiced_vials",
                  "duplicate_posting_vials", "unexplained_vials", "real_difference_vials", "naive_difference_vials",
                  "difference_value_synthetic", "real_difference_value_synthetic"):
            s[k] = round(sum(r[k] for r in rows), 2)
        s["gross_difference_vials"] = sum(abs(r["difference_vials"]) for r in rows)
        s["gross_timing_vials"] = sum(abs(r["timing_vials"]) for r in rows)
        s["cells_with_difference"] = sum(1 for r in rows if r["difference_vials"])
        s["cells_with_real_difference"] = sum(1 for r in rows if r["real_difference_vials"])
        out.append(s)
    return out


def chart(summary):
    plt = P.mpl()
    CHARTS.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    x = [datetime.fromisoformat(s["month_end"]).strftime("%b") for s in summary]
    series = [("timing_vials", "Timing (reverses next month)", "#a8a69f"),
              ("writeoff_not_booked_vials", "Write-off not booked (real shortage)", "#d03b3b"),
              ("receipt_not_invoiced_vials", "Receipt not invoiced", "#eb6834"),
              ("duplicate_posting_vials", "Duplicate posting in accounting", "#eda100")]
    pos = [0] * len(x)
    neg = [0] * len(x)
    for key, label, color in series:
        vals = [s[key] for s in summary]
        bottoms = [p if v >= 0 else n for v, p, n in zip(vals, pos, neg)]
        ax.bar(x, vals, bottom=bottoms, color=color, label=label, width=0.6, zorder=2)
        pos = [p + max(v, 0) for p, v in zip(pos, vals)]
        neg = [n + min(v, 0) for n, v in zip(neg, vals)]
    ax.plot(x, [s["naive_difference_vials"] for s in summary], color="#2a78d6", lw=1.6, ls="--", marker="o", ms=4,
            label="Naive difference (cartons not converted)", zorder=3)
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Vials (operational - accounting)")
    lo = min(neg + [s["naive_difference_vials"] for s in summary])
    hi = max(pos + [s["naive_difference_vials"] for s in summary])
    ax.set_ylim(lo - 4, hi + 4)
    ax.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    ax.set_title("Month-end inventory difference, explained vial by vial", loc="left", fontsize=13, fontweight="bold",
                 color="#0b0b0b", pad=24)
    ax.text(0, 1.02, "Network total, 2026 month ends. Timing reverses; the coloured segments persist until someone books them.",
            transform=ax.transAxes, fontsize=9.5, color="#52514e")
    fig.text(0.01, 0.01, P.DISCLAIMER + " | Coralline Infusion Network (fictional)", fontsize=7.5, color="#6f6d68")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CHARTS / "recon_by_month.png", dpi=160, facecolor="#fcfcfb")
    plt.close(fig)


def main():
    con = P.connect()
    opening, events = load(con)
    recon, items = reconcile(opening, events)
    summary = summarize(recon)
    for name, rows in [("opening_positions", opening), ("recon_month_end", recon), ("reconciling_items", items),
                       ("recon_summary", summary)]:
        P.write_csv(rows, OUT / f"{name}.csv")
    chart(summary)
    sep = summary[-1]
    print(f"#20 built: Sep 30 difference {sep['difference_vials']:+} vials = timing {sep['timing_vials']:+} + real "
          f"{sep['difference_vials'] - sep['timing_vials']:+}; unexplained {sum(s['unexplained_vials'] for s in summary)}")


if __name__ == "__main__":
    main()
