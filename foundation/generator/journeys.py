"""Patient journeys: referral -> order -> authorization -> appointments -> administrations.

The simulation runs the full timeline (past the snapshot date where needed), then
`as_of_view` cuts it at AS_OF exactly the way a source-system snapshot would:
future decisions are unknown, late status updates have not arrived yet, and only
appointments already booked are visible.
"""
import math
from datetime import timedelta

from . import config as C
from .util import (add_business_days, business_days_between, next_business_day, office_time,
                   poisson, slot_time, stream, weighted)

STAGE_RANK = {"Intake": 1, "Benefits Verification": 2, "Prior Authorization": 3,
              "Ready to Schedule": 4, "Active": 5, "On Hold": 5,
              "Completed": 6, "Discontinued": 6, "Cancelled": 6}
TERMINAL = {"Completed", "Discontinued", "Cancelled"}
UMBRELLA = {k: dict(share=s, denial=d, tat=t, pa_mult=m) for k, _, _, s, d, t, m in C.PAYER_UMBRELLAS}
S08_OPENED = next(o for k, _, _, o, _ in C.SITES if k == "S08")
COUNTY_STATE = {k: s for k, _, s, _, _ in C.COUNTIES}


class _Ids:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return self.n


def site_for(county_key, d):
    site = C.COUNTY_TO_SITE[county_key]
    if site == "S08" and d < S08_OPENED:
        return C.FALLBACK_SITE["S08"]
    return site


# --------------------------------------------------------------------------
# Intake: when new patients arrive and who referred them
# --------------------------------------------------------------------------
def _active_providers(profiles, d, specialty=None, exclude=None):
    return [(k, p["weight"]) for k, p in profiles.items()
            if p["weight"] > 0 and p["start"] <= d and (p["end"] is None or d < p["end"])
            and (specialty is None or p["specialty"] == specialty) and k != exclude]


def build_intake(profiles):
    rng = stream("intake")
    span = (C.AS_OF - C.DATA_START).days
    seasonal = {12: 0.75, 1: 0.95, 7: 0.90, 8: 0.95}
    county_weights = {s: [(k, w) for k, _, st, w, _ in C.COUNTIES if st == s] for s in ("GA", "SC", "NC")}
    intakes = []
    for d in business_days_between(C.DATA_START, C.AS_OF):
        t = (d - C.DATA_START).days / span
        lam = (3.15 + 2.5 * t) * seasonal.get(d.month, 1.0)
        for _ in range(poisson(rng, lam)):
            provider = weighted(rng, _active_providers(profiles, d))
            ref_day = d if rng.random() < 0.7 or d == C.DATA_START else add_business_days(d, -1)
            referral_at = office_time(rng, ref_day, 8, 16)
            created_at = office_time(rng, d, 8, 17)
            if created_at <= referral_at:
                created_at = referral_at + timedelta(minutes=rng.randrange(10, 180))
            pcounty = profiles[provider]["county"]
            county = pcounty if rng.random() < 0.7 else weighted(rng, county_weights[COUNTY_STATE[pcounty]])
            intakes.append(dict(created_at=created_at, referral_at=referral_at, provider=provider,
                                county=county, tiebreak=rng.random()))
    intakes.sort(key=lambda x: (x["created_at"], x["tiebreak"]))
    patients = []
    for i, it in enumerate(intakes, 1):
        it["patient_key"] = f"PT{i:05d}"
        patients.append(dict(patient_key=it["patient_key"], created_at=it["created_at"],
                             home_region_code=it["county"], home_state=COUNTY_STATE[it["county"]],
                             primary_site_key=site_for(it["county"], it["created_at"].date())))
    return patients, intakes


# --------------------------------------------------------------------------
# Insurance coverage intervals
# --------------------------------------------------------------------------
def build_coverage(patients, plans_by_umbrella):
    rng = stream("coverage")
    umbrella_weights = [(k, u["share"]) for k, u in UMBRELLA.items()]

    def pick_plan(avoid_umbrella=None):
        umbrella = weighted(rng, umbrella_weights)
        if avoid_umbrella and umbrella == avoid_umbrella and rng.random() < 0.8:
            umbrella = weighted(rng, [(k, w) for k, w in umbrella_weights if k != avoid_umbrella])
        return weighted(rng, plans_by_umbrella[umbrella]), umbrella

    rows = []
    for p in patients:
        created = p["created_at"].date()
        start = created - timedelta(days=rng.randrange(30, 900))
        if rng.random() < 0.20:
            prior_start = start - timedelta(days=rng.randrange(200, 800))
            plan, _ = pick_plan()
            rows.append(dict(patient_key=p["patient_key"], plan_key=plan, effective_from=prior_start,
                             effective_to=start - timedelta(days=1)))
        boundaries = [start]
        room = (C.AS_OF - created).days - 10
        if room > 30 and rng.random() < 0.35:
            d1 = created + timedelta(days=rng.randrange(20, room))
            boundaries.append(d1)
            if rng.random() < 0.35 and (C.AS_OF - d1).days > 70:
                d2 = d1 + timedelta(days=rng.randrange(60, min(400, (C.AS_OF - d1).days)))
                boundaries.append(d2)
        umbrella = None
        for i, b in enumerate(boundaries):
            plan, umbrella = pick_plan(avoid_umbrella=umbrella)
            end = boundaries[i + 1] - timedelta(days=1) if i + 1 < len(boundaries) else None
            rows.append(dict(patient_key=p["patient_key"], plan_key=plan, effective_from=b, effective_to=end))
    rows = _brand_switches(rows, plans_by_umbrella)
    rows.sort(key=lambda r: (r["patient_key"], r["effective_from"]))
    for i, r in enumerate(rows, 1):
        r["coverage_key"] = f"CV{i:05d}"
        r["coverage_rank"] = "Primary"
    return rows


def _brand_switches(rows, plans_by_umbrella):
    """Split some intervals into two brands of the SAME payer umbrella (e.g. a marketplace plan
    renewing under a sister brand). Umbrella-level coverage is unchanged, so payer behavior in the
    journey simulation is unaffected; only plan-level counts see the patient twice."""
    rng = stream("coverage-brands")
    plan_umbrella = {pk: u for u, plans in plans_by_umbrella.items() for pk, _ in plans}
    out = []
    for r in rows:
        umbrella = plan_umbrella[r["plan_key"]]
        siblings = [pk for pk, _ in plans_by_umbrella[umbrella] if pk != r["plan_key"]]
        end = r["effective_to"] or C.AS_OF
        share = 0.30 if umbrella == "PU08" else 0.08
        if siblings and (end - r["effective_from"]).days > 150 and rng.random() < share:
            split = r["effective_from"] + timedelta(days=rng.randrange(60, (end - r["effective_from"]).days - 30))
            out.append(dict(r, effective_to=split - timedelta(days=1)))
            out.append(dict(r, plan_key=rng.choice(siblings), effective_from=split))
        else:
            out.append(r)
    return out


def coverage_index(coverage):
    idx = {}
    for r in coverage:
        idx.setdefault(r["patient_key"], []).append(r)
    return idx


def plan_at(cov_idx, patient_key, d):
    for r in cov_idx.get(patient_key, []):
        if r["effective_from"] <= d and (r["effective_to"] is None or d <= r["effective_to"]):
            return r["plan_key"]
    return None


# --------------------------------------------------------------------------
# Journey simulation
# --------------------------------------------------------------------------
class Journeys:
    def __init__(self, profiles, cov_idx, plan_umbrella):
        self.rng = stream("journeys")
        self.ids = _Ids()
        self.profiles = profiles
        self.cov_idx = cov_idx
        self.plan_umbrella = plan_umbrella
        self.referrals, self.orders, self.events = [], [], []
        self.auths, self.decisions = [], []
        self.appts, self.admins, self.changes = [], [], []

    # -- small record helpers ------------------------------------------------
    def referral(self, patient_key, provider, when, kind):
        rec = dict(_id=self.ids.next(), patient_key=patient_key, provider=provider, referral_at=when,
                   source_category=weighted(self.rng, C.REFERRAL_SOURCES), referral_type=kind)
        self.referrals.append(rec)
        return rec

    def event(self, order, stage, when, reason=None):
        self.events.append(dict(order_id=order["_id"], stage=stage, event_at=when, reason=reason))
        order["_events"].append((when, stage, reason))

    def change(self, appt, when, change_type, new_status):
        self.changes.append(dict(appt_id=appt["_id"], changed_at=when, change_type=change_type,
                                 new_status=new_status))

    # -- per patient ---------------------------------------------------------
    def run(self, patients, intakes):
        by_key = {it["patient_key"]: it for it in intakes}
        for p in patients:
            it = by_key[p["patient_key"]]
            self.patient(p, it)

    def patient(self, p, it):
        rng = self.rng
        pk = p["patient_key"]
        first = self.referral(pk, it["provider"], it["referral_at"], "New patient")
        if rng.random() < 0.06:
            dup_at = office_time(rng, add_business_days(it["referral_at"].date(), rng.randint(1, 6)))
            self.referral(pk, it["provider"], dup_at, "Duplicate")
        if rng.random() < 0.07:
            return  # referral closed at intake, no order series
        spec = self.profiles[it["provider"]]["specialty"]
        therapy = weighted(rng, C.SPECIALTY_THERAPY[spec])
        order_at = office_time(rng, add_business_days(p["created_at"].date(), rng.randint(0, 3)))
        if order_at <= p["created_at"]:
            order_at = p["created_at"] + timedelta(minutes=rng.randrange(5, 90))
        queue = [(first, therapy, order_at, "New patient", None)]
        # A small share of patients later get an unrelated referral from another specialty.
        if rng.random() < 0.05:
            later = p["created_at"].date() + timedelta(days=rng.randrange(60, 500))
            if later < C.AS_OF:
                later = next_business_day(later)
                other = [s for s in C.SPECIALTY_THERAPY if s != spec]
                spec2 = rng.choice(other)
                cands = _active_providers(self.profiles, later, specialty=spec2)
                if cands:
                    prov2 = weighted(rng, cands)
                    ref2 = self.referral(pk, prov2, office_time(rng, later), "New therapy")
                    t2 = weighted(rng, C.SPECIALTY_THERAPY[spec2])
                    queue.append((ref2, t2, office_time(rng, add_business_days(later, rng.randint(0, 3))),
                                  "New therapy", None))
        while queue:
            ref, therapy, order_at, kind, earliest = queue.pop(0)
            queue.extend(self.order(p, ref, therapy, order_at, kind, earliest))

    # -- per order -----------------------------------------------------------
    def order(self, p, ref, therapy_key, created_at, kind, earliest_start):
        rng = self.rng
        t = C.THERAPIES[therapy_key]
        pk = p["patient_key"]
        county = p["home_region_code"]
        if created_at <= ref["referral_at"]:   # same-day times must still be in order
            created_at = ref["referral_at"] + timedelta(minutes=rng.randrange(5, 120))
        order = dict(_id=self.ids.next(), patient_key=pk, referral_id=ref["_id"], therapy_key=therapy_key,
                     site_key=site_for(county, created_at.date()), created_at=created_at, order_type=kind,
                     archived_at=None, _events=[], _first_dose_at=None)
        self.orders.append(order)
        self.event(order, "Intake", created_at)
        spawned = []

        def close(stage, when, reason):
            self.event(order, stage, when, reason)
            order["archived_at"] = when + timedelta(days=rng.randint(0, 5), hours=rng.randint(0, 3))

        bv_day = add_business_days(created_at.date(), rng.randint(1, 4))
        bv_at = office_time(rng, bv_day)
        self.event(order, "Benefits Verification", bv_at)
        if rng.random() < 0.05:
            close("Cancelled", office_time(rng, add_business_days(bv_day, rng.randint(2, 10))),
                  weighted(rng, C.CANCEL_REASONS_PRE))
            return spawned

        plan = plan_at(self.cov_idx, pk, bv_day)
        umbrella = UMBRELLA[self.plan_umbrella.get(plan, "PU99")]
        if rng.random() < t["pa_rate"] * umbrella["pa_mult"]:
            req_at = office_time(rng, add_business_days(bv_day, rng.randint(0, 2)))
            if req_at <= bv_at:
                req_at = bv_at + timedelta(minutes=rng.randrange(30, 240))
            self.event(order, "Prior Authorization", req_at)
            ready_at = None
            for attempt in (1, 2):
                plan_req = plan_at(self.cov_idx, pk, req_at.date())
                auth = dict(_id=self.ids.next(), order_id=order["_id"], patient_key=pk, plan_key=plan_req,
                            requested_at=req_at, request_sequence=attempt, _decisions=[])
                self.auths.append(auth)
                tat = max(1, round(rng.lognormvariate(math.log(umbrella["tat"]), 0.5)))
                decided_at = office_time(rng, next_business_day(req_at.date() + timedelta(days=tat)))
                if decided_at <= req_at:
                    decided_at = req_at + timedelta(hours=rng.randint(1, 6))
                if tat > 2 and rng.random() < 0.20:
                    pend_at = office_time(rng, next_business_day(req_at.date() + timedelta(days=rng.randint(1, tat - 1))))
                    if req_at < pend_at < decided_at:
                        auth["_decisions"].append((pend_at, "Pended - info requested"))
                approve_p = 1 - umbrella["denial"] if attempt == 1 else 0.55
                approved = rng.random() < approve_p
                auth["_decisions"].append((decided_at, "Approved" if approved else "Denied"))
                if approved:
                    ready_at = decided_at + timedelta(hours=rng.randint(1, 20))
                    break
                if attempt == 1 and rng.random() < 0.60:
                    req_at = office_time(rng, next_business_day(decided_at.date() + timedelta(days=rng.randint(3, 12))))
                    continue
                close("Cancelled", office_time(rng, add_business_days(decided_at.date(), rng.randint(1, 5))),
                      "Insurance denial")
                return spawned
        else:
            ready_at = office_time(rng, add_business_days(bv_day, rng.randint(1, 3)))
        self.event(order, "Ready to Schedule", ready_at)

        # ---- appointments --------------------------------------------------
        first_day = add_business_days(ready_at.date(), rng.randint(3, 15))
        if earliest_start and first_day < earliest_start:
            first_day = next_business_day(earliest_start)
        loading = [] if kind == "Renewal" else list(t["loading"])
        offsets = self._dose_offsets(loading, t["interval"], rng.randint(*t["doses"]))
        vials = rng.randint(*t["vials"])
        planned_day = first_day
        dose_index, doses_done = 0, 0
        last_start, prev_booking_anchor = None, ready_at
        pre_dose_cancel = rng.random() < 0.04
        while doses_done < len(offsets):
            start = slot_time(rng, next_business_day(planned_day))
            if start.date() > C.FUTURE_END:
                break
            appt = self._new_appt(p, order, start, prev_booking_anchor)
            if pre_dose_cancel and doses_done == 0:
                cancel_at = self._cancel_time(appt)
                self._finish(appt, "Cancelled", cancel_at, "Cancelled")
                close("Cancelled", cancel_at + timedelta(days=rng.randint(0, 3)),
                      weighted(rng, [("Patient choice", .4), ("Physician choice", .3), ("Clinical issue", .3)]))
                return spawned
            r = rng.random()
            if r < 0.055:
                cancel_at = self._cancel_time(appt)
                self._finish(appt, "Cancelled", cancel_at, "Cancelled")
                prev_booking_anchor = cancel_at
                planned_day = add_business_days(start.date(), rng.randint(2, 7))
                continue
            if r < 0.08:
                ns_at = start + timedelta(hours=rng.randint(1, 4))
                self._finish(appt, "No Show", ns_at, "No Show")
                prev_booking_anchor = ns_at
                planned_day = add_business_days(start.date(), rng.randint(2, 7))
                continue
            done_at = self._completion_time(start)
            self._finish(appt, "Complete", done_at, "Completed")
            prev_booking_anchor = start + timedelta(hours=2)
            if rng.random() < 0.035:
                appt["meds_administered"] = 0          # visit happened, drug held
                if rng.random() < 0.40:                # drug was prepared, then wasted
                    self._admin_line(appt, therapy_key, vials, start, administered=0)
                planned_day = add_business_days(start.date(), rng.randint(3, 10))
                continue
            appt["meds_administered"] = 1
            self._dose_lines(appt, therapy_key, vials, start)
            doses_done += 1
            last_start = start
            if order["_first_dose_at"] is None:
                order["_first_dose_at"] = start
                self.event(order, "Active", start + timedelta(minutes=rng.randint(30, 150)))
            if doses_done >= len(offsets):
                break
            if rng.random() < t["disc_hazard"]:
                reason = weighted(rng, C.DISCONTINUE_REASONS)
                disc_at = office_time(rng, add_business_days(start.date(), rng.randint(3, 20)))
                close("Discontinued", disc_at, reason)
                if reason == "Therapy change":
                    spec = self.profiles[ref["provider"]]["specialty"]
                    options = {k: w for k, w in C.SPECIALTY_THERAPY[spec].items() if k != therapy_key}
                    new_t = weighted(rng, options)
                    ref_at = office_time(rng, add_business_days(disc_at.date(), rng.randint(0, 8)))
                    if ref_at.date() <= C.AS_OF:
                        new_ref = self.referral(p["patient_key"], ref["provider"], ref_at, "New therapy")
                        spawned.append((new_ref, new_t, office_time(rng, add_business_days(ref_at.date(), rng.randint(0, 2))),
                                        "New therapy", None))
                return spawned
            hold_days = 0
            if rng.random() < 0.015:
                hold_at = office_time(rng, add_business_days(start.date(), rng.randint(1, 5)))
                hold_days = rng.randint(14, 45)
                self.event(order, "On Hold", hold_at, "Clinical hold")
                self.event(order, "Active", office_time(rng, next_business_day(hold_at.date() + timedelta(days=hold_days))),
                           "Hold released")
            gap = offsets[doses_done] - offsets[doses_done - 1]
            planned_day = start.date() + timedelta(days=gap + hold_days + rng.randint(-2, 3))

        if doses_done >= len(offsets) and last_start is not None:
            renew = rng.random() < t["renewal"]
            done_at = office_time(rng, add_business_days(last_start.date(), rng.randint(1, 10)))
            close("Completed", done_at, "Renewed - new order series" if renew else "Course complete")
            if renew:
                ref_day = last_start.date() - timedelta(days=rng.randint(5, 30))
                ref_day = max(ref_day, order["_first_dose_at"].date() + timedelta(days=1))
                if ref_day <= C.AS_OF:
                    prov = ref["provider"]
                    if rng.random() < 0.15:
                        spec = self.profiles[prov]["specialty"]
                        cands = _active_providers(self.profiles, ref_day, specialty=spec, exclude=prov)
                        if cands:
                            prov = weighted(rng, cands)
                    new_ref = self.referral(p["patient_key"], prov, office_time(rng, next_business_day(ref_day)), "Renewal")
                    order_at = office_time(rng, add_business_days(new_ref["referral_at"].date(), rng.randint(0, 2)))
                    spawned.append((new_ref, therapy_key, order_at, "Renewal",
                                    last_start.date() + timedelta(days=t["interval"] or 28)))
        return spawned

    # -- appointment helpers -------------------------------------------------
    @staticmethod
    def _dose_offsets(loading, interval, n_doses):
        offsets = list(loading[:n_doses])
        last = offsets[-1] if offsets else -interval
        while len(offsets) < n_doses:
            last += interval
            offsets.append(last)
        return offsets

    def _new_appt(self, p, order, start, anchor):
        rng = self.rng
        lead = (start - anchor).days
        if lead > 60:
            booked_at = office_time(rng, add_business_days(start.date(), -rng.randint(15, 35)))
        else:
            booked_at = anchor + timedelta(hours=rng.randint(1, 30))
        if booked_at >= start - timedelta(hours=12):
            booked_at = start - timedelta(days=1, hours=rng.randint(0, 6))
        appt = dict(_id=self.ids.next(), patient_key=p["patient_key"], order_id=order["_id"],
                    site_key=site_for(p["home_region_code"], start.date()), therapy_key=order["therapy_key"],
                    start_local=start, booked_at=booked_at, meds_administered=0, _final=None)
        self.appts.append(appt)
        self.change(appt, booked_at, "Booked", "Scheduled")
        if rng.random() < 0.6:
            conf = office_time(rng, add_business_days(start.date(), -rng.randint(1, 3)))
            if booked_at < conf < start:
                appt["_confirm_at"] = conf
        return appt

    def _finish(self, appt, status, when, change_type):
        """Record the visit outcome; a reminder call only counts if it came first."""
        conf = appt.get("_confirm_at")
        if conf and conf < when:
            self.change(appt, conf, "Confirmed", "Confirmed")
        appt["_final"] = (status, when)
        self.change(appt, when, change_type, status)

    def _cancel_time(self, appt):
        rng = self.rng
        start, booked = appt["start_local"], appt["booked_at"]
        when = office_time(rng, start.date() - timedelta(days=rng.randint(0, 5)), 7, 12)
        if when <= booked:
            when = booked + timedelta(hours=1)
        if when >= start:
            when = start - timedelta(minutes=30)
        return when

    def _completion_time(self, start):
        rng = self.rng
        if rng.random() < 0.88:
            return start + timedelta(hours=rng.randint(2, 6), minutes=rng.randrange(0, 60))
        return office_time(rng, add_business_days(start.date(), rng.randint(1, 10)))

    def _admin_line(self, appt, therapy_key, vials, start, administered=1, line=1, lot=None):
        rng = self.rng
        lot = lot or f"LOT-{therapy_key[-1]}{start.year % 100:02d}{rng.randrange(1000, 9999)}"
        self.admins.append(dict(appt_id=appt["_id"], therapy_key=therapy_key, administered_flag=administered,
                                vials=vials, lot_code=lot, line_number=line,
                                administered_at=start + timedelta(minutes=rng.randint(20, 150))))

    def _dose_lines(self, appt, therapy_key, vials, start):
        rng = self.rng
        v = vials if rng.random() > 0.05 else max(1, vials + rng.choice([-1, 1]))
        if v >= 2 and rng.random() < 0.06:          # split across two lots -> two line items
            first = rng.randint(1, v - 1)
            self._admin_line(appt, therapy_key, first, start, line=1)
            self._admin_line(appt, therapy_key, v - first, start, line=2)
            lines = 2
        else:
            self._admin_line(appt, therapy_key, v, start, line=1)
            lines = 1
        if rng.random() < 0.04:                      # add-on pre-medication line
            self._admin_line(appt, "THERAPY_K", 1, start, line=lines + 1)
