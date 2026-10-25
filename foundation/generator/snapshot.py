"""Cut the simulated timeline at AS_OF and assign final, sortable keys."""
from datetime import datetime, time, timedelta

from . import config as C
from .journeys import TERMINAL
from .util import to_utc

CUTOFF = datetime.combine(C.AS_OF, time(23, 59, 59))


def _keyed(rows, sort_key, prefix, width):
    rows.sort(key=sort_key)
    for i, r in enumerate(rows, 1):
        r["_key"] = f"{prefix}{i:0{width}d}"
    return rows


def as_of_view(j, patients):
    out = {}

    # Referrals ----------------------------------------------------------------
    refs = [r for r in j.referrals if r["referral_at"] <= CUTOFF]
    _keyed(refs, lambda r: (r["referral_at"], r["patient_key"], r["_id"]), "RF", 5)
    ref_key = {r["_id"]: r["_key"] for r in refs}
    out["referrals"] = [dict(referral_key=r["_key"], patient_key=r["patient_key"], provider_key=r["provider"],
                             referral_at=r["referral_at"], source_category=r["source_category"],
                             referral_type=r["referral_type"]) for r in refs]

    # Orders and their status history -------------------------------------------
    orders = [o for o in j.orders if o["created_at"] <= CUTOFF]
    _keyed(orders, lambda o: (o["created_at"], o["patient_key"], o["_id"]), "OS", 5)
    order_key = {o["_id"]: o["_key"] for o in orders}
    out["orders"], events = [], []
    for o in orders:
        evs = sorted([e for e in o["_events"] if e[0] <= CUTOFF], key=lambda e: e[0])
        stage_at, stage, reason = evs[-1]
        prev = None
        for seq, (when, st, why) in enumerate(evs, 1):
            events.append(dict(order_key=o["_key"], previous_stage=prev, new_stage=st, event_at=when,
                               reason=why, correction_flag=0, _seq=seq))
            prev = st
        archived = o["archived_at"] if o["archived_at"] and o["archived_at"] <= CUTOFF else None
        out["orders"].append(dict(
            order_key=o["_key"], patient_key=o["patient_key"], referral_key=ref_key[o["referral_id"]],
            therapy_key=o["therapy_key"], site_key=o["site_key"], order_type=o["order_type"],
            created_at=o["created_at"], stage=stage, stage_updated_at=stage_at, archived_at=archived,
            terminal_reason=reason if stage in TERMINAL else None))
    _keyed(events, lambda e: (e["event_at"], e["order_key"], e["_seq"]), "SE", 6)
    out["order_status_events"] = [dict(status_event_key=e["_key"], order_key=e["order_key"],
                                       previous_stage=e["previous_stage"], new_stage=e["new_stage"],
                                       event_at=e["event_at"], reason=e["reason"],
                                       correction_flag=e["correction_flag"]) for e in events]

    # Authorizations ------------------------------------------------------------
    auths = [a for a in j.auths if a["requested_at"] <= CUTOFF and a["order_id"] in order_key]
    _keyed(auths, lambda a: (a["requested_at"], order_key[a["order_id"]], a["_id"]), "AU", 5)
    out["authorizations"], decisions = [], []
    for a in auths:
        known = [d for d in a["_decisions"] if d[0] <= CUTOFF]
        final = [d for d in known if d[1] in ("Approved", "Denied")]
        out["authorizations"].append(dict(
            auth_key=a["_key"], order_key=order_key[a["order_id"]], patient_key=a["patient_key"],
            plan_key_at_request=a["plan_key"], requested_at=a["requested_at"],
            request_sequence=a["request_sequence"],
            decision_at=final[-1][0] if final else None, decision_result=final[-1][1] if final else None,
            as_of_status=final[-1][1] if final else "Pending"))
        for when, result in known:
            decisions.append(dict(auth_key=a["_key"], decision_at=when, decision_result=result))
    _keyed(decisions, lambda d: (d["decision_at"], d["auth_key"]), "DC", 5)
    out["authorization_decisions"] = [dict(decision_key=d["_key"], auth_key=d["auth_key"],
                                           decision_at=d["decision_at"], decision_result=d["decision_result"])
                                      for d in decisions]

    # Appointments, change log, administrations ---------------------------------
    changes_by_appt = {}
    for c in j.changes:
        changes_by_appt.setdefault(c["appt_id"], []).append(c)
    appts = [a for a in j.appts if a["booked_at"] <= CUTOFF and a["order_id"] in order_key]
    _keyed(appts, lambda a: (a["start_local"], a["patient_key"], a["_id"]), "AP", 6)
    appt_key = {a["_id"]: a["_key"] for a in appts}
    first_start = {}
    for a in appts:
        if a["patient_key"] not in first_start or a["start_local"] < first_start[a["patient_key"]][0]:
            first_start[a["patient_key"]] = (a["start_local"], a["_id"])
    first_ids = {v[1] for v in first_start.values()}

    out["appointments"], changes, completed_ids = [], [], set()
    for a in appts:
        visible = sorted([c for c in changes_by_appt[a["_id"]] if c["changed_at"] <= CUTOFF],
                         key=lambda c: c["changed_at"])
        status = visible[-1]["new_status"]
        if status == "Complete":
            completed_ids.add(a["_id"])
        prev = None
        for c in visible:
            changes.append(dict(appt_key=a["_key"], changed_at=c["changed_at"], change_type=c["change_type"],
                                old_status=prev, new_status=c["new_status"]))
            prev = c["new_status"]
        out["appointments"].append(dict(
            appt_key=a["_key"], patient_key=a["patient_key"], order_key=order_key[a["order_id"]],
            site_key=a["site_key"], therapy_key=a["therapy_key"], start_local=a["start_local"],
            start_utc=to_utc(a["start_local"]), booked_at=a["booked_at"], status=status,
            meds_administered=a["meds_administered"] if status == "Complete" else 0,
            first_patient_appt_flag=1 if a["_id"] in first_ids else 0, updated_at=visible[-1]["changed_at"]))
    _keyed(changes, lambda c: (c["changed_at"], c["appt_key"]), "CL", 6)
    out["appointment_change_log"] = [dict(change_key=c["_key"], appt_key=c["appt_key"], changed_at=c["changed_at"],
                                          change_type=c["change_type"], old_status=c["old_status"],
                                          new_status=c["new_status"]) for c in changes]

    admins = [ad for ad in j.admins if ad["appt_id"] in completed_ids]
    _keyed(admins, lambda ad: (ad["administered_at"], appt_key[ad["appt_id"]], ad["line_number"]), "AD", 6)
    out["administrations"] = [dict(admin_key=ad["_key"], appt_key=appt_key[ad["appt_id"]],
                                   therapy_key=ad["therapy_key"], administered_flag=ad["administered_flag"],
                                   vials=ad["vials"], lot_code=ad["lot_code"], line_number=ad["line_number"],
                                   administered_at=ad["administered_at"]) for ad in admins]

    # Patient state as of the snapshot -------------------------------------------
    last_treated, future, open_orders, any_order = {}, set(), set(), set()
    for a in out["appointments"]:
        if a["status"] == "Complete" and a["meds_administered"] == 1:
            last_treated[a["patient_key"]] = max(last_treated.get(a["patient_key"], a["start_local"]), a["start_local"])
        if a["start_local"] > CUTOFF and a["status"] in ("Scheduled", "Confirmed"):
            future.add(a["patient_key"])
    for o in out["orders"]:
        any_order.add(o["patient_key"])
        if o["stage"] not in TERMINAL:
            open_orders.add(o["patient_key"])
    recent = CUTOFF - timedelta(days=120)
    out["patients"] = []
    for p in patients:
        k = p["patient_key"]
        if k in future or (k in last_treated and last_treated[k] >= recent):
            state = "Active"
        elif k in open_orders and k not in last_treated:
            state = "Pending start"
        elif k in any_order:
            state = "Inactive"
        else:
            state = "Closed at intake"
        out["patients"].append(dict(p, current_state=state))
    return out
