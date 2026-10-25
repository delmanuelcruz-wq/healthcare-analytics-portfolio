"""Extension tables added in generator v1.1.0 for the Tier 3 micro-cases.

- Pharmacy delivery tickets (workstream 08): prescriptions, fills and the delivery
  tickets a specialty pharmacy sends for three mock therapies.
- Accounting inventory ledger (workstream 20): the books' view of the same drug
  inventory that the operational ledger tracks, posted with realistic lags.

Each family draws from its own random stream and only *reads* the core tables, so
every v1.0.0 CSV stays byte-identical. New planted defects are appended to the
register after the original rows (their exception ids continue the sequence).
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from . import config as C
from .util import add_business_days, office_time, stream

CUTOFF = datetime.combine(C.AS_OF, time(23, 59, 59))

# --------------------------------------------------------------------------
# Pharmacy deliveries (workstream 08)
# --------------------------------------------------------------------------
PHARMACY_THERAPIES = ("THERAPY_A", "THERAPY_C", "THERAPY_I")
PHARMACY_START = datetime(2026, 7, 1)
PHARMACIES = ["Bayline Specialty Pharmacy (fictional)", "Seabreeze Specialty Rx (fictional)"]
RECEIVER_ROLES = [("Site pharmacist (role)", .45), ("Charge nurse (role)", .40), ("Site coordinator (role)", .15)]


def fill_ref(rx_key, fill_number):
    """How the pharmacy feed types the fill: bare Rx for the original, -R<n> suffix for refill n."""
    return rx_key if fill_number == 0 else f"{rx_key}-R{fill_number}"


def build_pharmacy(t, reg):
    rng = stream("pharmacy")
    appts = sorted(t["appointments"], key=lambda a: (a["start_local"], a["appt_key"]))
    horizon = CUTOFF + timedelta(days=6)
    picked = [a for a in appts if a["therapy_key"] in PHARMACY_THERAPIES and a["site_key"]
              and ((a["status"] == "Complete" and a["meds_administered"] == 1 and PHARMACY_START <= a["start_local"] <= CUTOFF)
                   or (a["status"] in ("Scheduled", "Confirmed") and CUTOFF < a["start_local"] <= horizon))]
    prior = defaultdict(int)                  # treated visits before the window -> refills continue from them
    for a in appts:
        if a["status"] == "Complete" and a["meds_administered"] == 1 and a["start_local"] < PHARMACY_START:
            prior[a["order_key"]] += 1
    vials = defaultdict(int)
    for ad in t["administrations"]:
        vials[(ad["appt_key"], ad["therapy_key"])] += ad["vials"] if ad["administered_flag"] == 1 else 0
    orders = {o["order_key"]: o for o in t["orders"]}
    by_order = defaultdict(list)
    for a in picked:
        by_order[a["order_key"]].append(a)

    prescriptions, fills, tickets = [], [], []
    for n, ok in enumerate(sorted(by_order, key=lambda k: (by_order[k][0]["start_local"], k)), 1):
        visits, o = by_order[ok], orders[ok]
        rx_key = f"RX{n:04d}"
        pharmacy = PHARMACIES[0] if rng.random() < 0.6 else PHARMACIES[1]
        rx_fills = []
        for i, a in enumerate(visits):
            fill_number = prior[ok] + i
            visit_day = a["start_local"].date()
            two_day = rng.random() < 0.2
            ship_day = add_business_days(visit_day, -(3 if two_day else 1))
            fill_day = add_business_days(ship_day, -rng.randint(1, 2))
            shipped_at = office_time(rng, ship_day, 12, 16)
            hours = rng.randint(40, 50) if two_day else rng.randint(14, 18)
            delivered_at = min(shipped_at + timedelta(hours=hours, minutes=rng.randint(0, 59)),
                               a["start_local"] - timedelta(hours=1, minutes=rng.randint(0, 59)))
            receiver = rng.choices([r for r, _ in RECEIVER_ROLES], [w for _, w in RECEIVER_ROLES])[0]
            cold_chain = 1 if rng.random() > 0.015 else 0
            qty = vials[(a["appt_key"], a["therapy_key"])] or rng.randint(*C.THERAPIES[a["therapy_key"]]["vials"])
            if fill_day > C.AS_OF:
                continue
            rx_fills.append(dict(rx_key=rx_key, fill_number=fill_number, for_appt_key=a["appt_key"],
                                 fill_date=fill_day, vials_dispensed=qty))
            if shipped_at > CUTOFF:
                continue
            delivered = delivered_at <= CUTOFF
            tickets.append(dict(fill_ref=fill_ref(rx_key, fill_number), site_key=a["site_key"],
                                service_level="2-day" if two_day else "Next day", shipped_at=shipped_at,
                                delivery_status="Delivered" if delivered else "In transit",
                                delivered_at=delivered_at if delivered else None,
                                received_by_role=receiver if delivered else None, cold_chain_ok=cold_chain,
                                _rx=rx_key, _fill_number=fill_number, _appt=a))
        if not rx_fills:
            continue
        first_fill = rx_fills[0]["fill_date"]
        written = max(o["created_at"].date(), first_fill - timedelta(days=60)) if prior[ok] == 0 else \
            first_fill - timedelta(days=rng.randint(60, 200))
        prescriptions.append(dict(rx_key=rx_key, order_key=ok, patient_key=o["patient_key"], therapy_key=o["therapy_key"],
                                  dispensing_pharmacy=pharmacy, written_date=min(written, first_fill),
                                  refills_authorized=rx_fills[-1]["fill_number"] + rng.randint(0, 3)))
        fills += rx_fills

    fills.sort(key=lambda f: (f["fill_date"], f["rx_key"], f["fill_number"]))
    fill_key = {}
    for i, f in enumerate(fills, 1):
        f["fill_key"] = f"FL{i:05d}"
        fill_key[(f["rx_key"], f["fill_number"])] = f["fill_key"]
    tickets.sort(key=lambda x: (x["shipped_at"], x["fill_ref"]))
    for i, x in enumerate(tickets, 1):
        x["ticket_key"] = f"DT{i:05d}"
        x["tracking_ref"] = f"TRK-MOCK-{rng.randrange(100000, 999999)}"

    # --- planted defects (disjoint picks) ---------------------------------------
    delivered = [x for x in tickets if x["delivery_status"] == "Delivered" and x["shipped_at"] < datetime(2026, 10, 15)]
    refills = [x for x in delivered if x["_fill_number"] > 0]
    orphans = rng.sample(refills, 3)
    rest = [x for x in delivered if x not in orphans]
    no_date = rng.sample(rest, 4)
    rest = [x for x in rest if x not in no_date]
    wrong_site = rng.sample(rest, 2)
    site_keys = [s[0] for s in C.SITES]
    for i, x in enumerate(orphans):
        intended = fill_key[(x["_rx"], x["_fill_number"])]
        if i < 2:   # letter O typed for the zero after "RX"
            x["fill_ref"] = "RXO" + x["fill_ref"][3:]
        else:       # suffix typed backwards
            x["fill_ref"] = f"{x['_rx']}-{x['_fill_number']}R"
        reg.add("injected_defect", "DELIVERY_ORPHAN_FILL_REF", "delivery_tickets", x["ticket_key"], intended,
                f"Fill reference typed as '{x['fill_ref']}'; it resolves to no prescription fill even after parsing.",
                "delivery tickets whose parsed fill reference matches no fill", "08")
    for x in no_date:
        x["delivered_at"] = None
        reg.add("injected_defect", "DELIVERY_MISSING_DELIVERED_AT", "delivery_tickets", x["ticket_key"], x["fill_ref"],
                "Ticket status is Delivered but the delivered timestamp is blank in the source feed.",
                "Delivered tickets with null delivered_at", "08")
    for x in wrong_site:
        correct = x["site_key"]
        x["site_key"] = sorted(s for s in site_keys if s != correct)[rng.randrange(len(site_keys) - 1)]
        reg.add("injected_defect", "DELIVERY_WRONG_SITE", "delivery_tickets", x["ticket_key"], correct,
                "Delivery ticket names a different site than the appointment the fill was shipped for.",
                "ticket site vs appointment site after the corrected join", "08")
    for x in tickets:
        for k in ("_rx", "_fill_number", "_appt"):
            x.pop(k)
    return prescriptions, fills, tickets


# --------------------------------------------------------------------------
# Accounting inventory ledger (workstream 20)
# --------------------------------------------------------------------------
LEDGER_START = date(2026, 1, 1)
UNIT_COST = {"THERAPY_D": 1850.00, "THERAPY_F": 2400.00, "THERAPY_G": 1125.00}   # invented, per vial
POSTING = {   # operational event -> (ledger entry type, business-day lag range)
    "RECEIPT": ("RECEIPT_INVOICE", (0, 5)), "ADMINISTERED": ("COGS_ISSUE", (1, 1)),
    "ADJ_WASTE": ("WASTE_WRITE_OFF", (1, 1)), "ADJ_EXPIRED": ("EXPIRY_WRITE_OFF", (1, 7)),
    "ADJ_COUNT": ("COUNT_ADJUSTMENT", (2, 8)), "RETURN_IN": ("RETURN_CREDIT", (1, 5)),
}


def _vials(x):
    return x["qty"] * C.VIALS_PER_CARTON[x["therapy_key"]] if x["unit_type"] == "CARTON" else x["qty"]


def build_accounting(t, reg):
    rng = stream("accounting")
    tx = sorted(t["inventory_transactions"], key=lambda x: x["inventory_event_key"])
    start = datetime.combine(LEDGER_START, time(0, 0))
    first_snap = {}
    for s in sorted(t["inventory_snapshots"], key=lambda s: s["week_start"]):
        first_snap.setdefault((s["site_key"], s["therapy_key"]), s)
    before = defaultdict(int)
    for x in tx:
        if x["event_at"] < start:
            before[(x["site_key"], x["therapy_key"])] += _vials(x)

    def line(site, therapy, posted, entry_type, source, qty):
        cost = UNIT_COST[therapy]
        return dict(site_key=site, therapy_key=therapy, posting_date=posted, fiscal_period=posted.strftime("%Y-%m"),
                    entry_type=entry_type, source_event_key=source, qty_vials=qty, fictional_unit_cost=cost,
                    fictional_amount=round(qty * cost, 2))

    # Both systems agreed at the Dec 31, 2025 close (synthetic opening balance).
    lines = [line(site, therapy, LEDGER_START - timedelta(days=1), "OPENING_BALANCE", None,
                  s["beginning_qty"] + before[(site, therapy)]) for (site, therapy), s in sorted(first_snap.items())]
    in_year = [x for x in tx if x["event_at"] >= start]
    lag = {x["inventory_event_key"]: rng.randint(*POSTING[x["event_type"]][1]) for x in in_year}

    def window(lo, hi):
        return [x for x in in_year if datetime(*lo) <= x["event_at"] < datetime(*hi) and x["unit_type"] == "VIAL"]

    write_offs = [x for x in window((2026, 2, 1), (2026, 9, 1))
                  if x["event_type"] == "ADJ_EXPIRED" or (x["event_type"] == "ADJ_COUNT" and x["qty"] < 0)]
    unbooked = rng.sample(write_offs, 2)
    receipts = window((2026, 3, 1), (2026, 9, 1))
    receipts = [x for x in receipts if x["event_type"] == "RECEIPT"]
    not_invoiced = rng.sample(receipts, 1)
    doubled = rng.sample([x for x in receipts if x not in not_invoiced], 1)
    skip = {x["inventory_event_key"] for x in unbooked + not_invoiced}

    dup_lines = []
    for x in in_year:
        key = x["inventory_event_key"]
        posted = add_business_days(x["event_at"].date(), lag[key])
        if key in skip or posted > C.AS_OF:
            continue
        entry_type = POSTING[x["event_type"]][0]
        lines.append(line(x["site_key"], x["therapy_key"], posted, entry_type, key, _vials(x)))
        if x in doubled:
            dup = line(x["site_key"], x["therapy_key"], add_business_days(posted, rng.randint(1, 3)), entry_type, key,
                       _vials(x))
            lines.append(dup)
            dup_lines.append(dup)
    lines.sort(key=lambda r: (r["posting_date"], r["site_key"], r["therapy_key"], r["entry_type"],
                              r["source_event_key"] or "", r["qty_vials"]))
    for i, r in enumerate(lines, 1):
        r["gl_line_key"] = f"GL{i:06d}"

    for x in unbooked:
        reg.add("injected_defect", "GL_WRITE_OFF_NOT_BOOKED", "inventory_transactions", x["inventory_event_key"],
                f"{x['site_key']}|{x['therapy_key']}",
                f"Operational write-off of {x['qty']:+d} vial(s) never posted to the accounting ledger - a real shortage "
                "the books still carry, not a timing difference.", "operational write-offs with no ledger line", "20")
    for x in not_invoiced:
        reg.add("injected_defect", "GL_RECEIPT_NOT_INVOICED", "inventory_transactions", x["inventory_event_key"],
                f"{x['site_key']}|{x['therapy_key']}",
                f"Receipt of {_vials(x)} vials is on hand operationally but was never invoiced into the books.",
                "operational receipts with no ledger line", "20")
    for d in dup_lines:
        reg.add("injected_defect", "GL_DUPLICATE_POSTING", "accounting_ledger", d["gl_line_key"], d["source_event_key"],
                "Receipt invoice posted twice to the accounting ledger (same source event).",
                "ledger lines sharing a source event and entry type", "20")
    return lines
