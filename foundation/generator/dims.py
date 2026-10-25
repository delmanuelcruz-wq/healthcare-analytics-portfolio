"""Dimension tables: geography, sites, therapies, payers, providers."""
from datetime import date, timedelta

from . import config as C
from .util import stream, weighted


def build_geography():
    counties = [dict(county_key=k, county_name=n, state_code=s, is_fictional=1)
                for k, n, s, _, _ in C.COUNTIES]
    crosswalk = []
    for k, _, _, _, zips in C.COUNTIES:
        for z in zips:
            crosswalk.append(dict(zip5=z, county_key=k, allocation_ratio=1.0, is_primary=1))
    zip5, parts = C.SPLIT_ZIP
    for county_key, ratio, primary in parts:
        crosswalk.append(dict(zip5=zip5, county_key=county_key, allocation_ratio=ratio, is_primary=primary))
    county_state = {k: s for k, _, s, _, _ in C.COUNTIES}
    sites = [dict(site_key=k, site_name=n + " (fictional)", county_key=c, state_code=county_state[c],
                  opened_date=o, chairs=ch, timezone="America/New_York")
             for k, n, c, o, ch in C.SITES]
    return counties, crosswalk, sites


def build_therapies():
    rows = []
    program_of = {t: p for p, spec in C.PROGRAMS.items() for t in spec["therapies"]}
    for key, t in C.THERAPIES.items():
        rows.append(dict(
            therapy_key=key, therapy_label=t["label"], route=t["route"],
            maintenance_interval_days=t["interval"], is_add_on_only=1 if key == "THERAPY_K" else 0,
            manufacturer_program=program_of.get(key), mock_billing_code=t["mock_code"],
            vials_per_carton=C.VIALS_PER_CARTON.get(key),
        ))
    return rows


def build_payers():
    umbrellas = [dict(umbrella_key=k, umbrella_name=n + " (fictional)", segment=seg,
                      is_top10=0 if k == "PU99" else 1)
                 for k, n, seg, *_ in C.PAYER_UMBRELLAS]
    plans, umbrella_map = [], []
    n = 0
    for umbrella_key, plan_list in C.PAYER_PLANS.items():
        for raw_name, _ in plan_list:
            n += 1
            plan_key = f"PLN{n:03d}"
            plans.append(dict(plan_key=plan_key, raw_plan_name=raw_name))
            umbrella_map.append(dict(plan_key=plan_key, umbrella_key=umbrella_key,
                                     mapping_source="analyst alias review", mapped_on=date(2026, 1, 15)))
    # Aliases present in source data but missing from the map (defect, see defects.py).
    unmapped = {}
    for raw_name, true_umbrella in C.UNMAPPED_PLAN_ALIASES:
        n += 1
        plan_key = f"PLN{n:03d}"
        plans.append(dict(plan_key=plan_key, raw_plan_name=raw_name))
        unmapped[plan_key] = true_umbrella
    return umbrellas, plans, umbrella_map, unmapped


def build_providers(n_providers=247, n_never_referred=15, n_multi_specialty=20):
    """Referring providers with hidden activity profiles.

    The activity window and referral propensity drive the simulation but are not
    exported: analysts only see referral events, as in real life.
    """
    rng = stream("providers")
    county_weights = [(k, w) for k, _, _, w, _ in C.COUNTIES]
    county_zips = {k: z for k, _, _, _, z in C.COUNTIES}
    spec_weights = [(code, w) for code, _, w in C.SPECIALTIES]

    # Group practices first, then place providers into them.
    practices, used_names = [], set()
    while len(practices) < 120:
        spec = weighted(rng, spec_weights)
        county = weighted(rng, county_weights)
        name = f"{rng.choice(C.PRACTICE_WORDS_A)} {C.PRACTICE_WORDS_B[spec]}"
        if name in used_names:
            county_word = next(n for k, n, *_ in C.COUNTIES if k == county).split()[0]
            name = f"{name} of {county_word}"
        if name in used_names:
            continue
        used_names.add(name)
        practices.append(dict(name=name + " (fictional)", specialty=spec, county=county,
                              zip5=rng.choice(county_zips[county]), size=rng.choice([1, 1, 2, 2, 3, 4])))

    # One seat per provider; practices with size 3 get three seats, and so on.
    seats = [p for p in practices for _ in range(p["size"])]
    i = 0
    while len(seats) < n_providers:
        seats.append(practices[i % len(practices)])
        i += 1
    seats = seats[:n_providers]

    providers, specialties, profiles = [], [], {}
    used_ids = set()
    for practice in seats:
        key = f"PRV{len(providers) + 1:04d}"
        while True:
            source_id = f"MOCKNPI-{rng.randrange(100000, 999999)}"
            if source_id not in used_ids:
                used_ids.add(source_id)
                break
        never = len(providers) >= n_providers - n_never_referred
        if never:
            start = C.DATA_START + timedelta(days=rng.randrange(0, (C.AS_OF - C.DATA_START).days))
            created = start
            end = None
            weight = 0.0
        else:
            established = rng.random() < 0.55
            if established:
                start = C.DATA_START
                created = date(2021, 1, 1) + timedelta(days=rng.randrange(0, (C.DATA_START - date(2021, 1, 1)).days))
            else:
                start = C.DATA_START + timedelta(days=rng.randrange(30, (C.AS_OF - C.DATA_START).days - 21))
                created = start - timedelta(days=rng.randrange(0, 21))
            end = None
            if rng.random() < 0.30 and (C.AS_OF - start).days > 120:
                end = start + timedelta(days=rng.randrange(60, (C.AS_OF - start).days))
            weight = min(rng.paretovariate(1.3), 12.0)   # heavy-tailed but capped: no single mega-referrer
        providers.append(dict(provider_key=key, source_identity_key=source_id,
                              primary_specialty=practice["specialty"], fictional_practice=practice["name"],
                              practice_zip5=practice["zip5"], created_date=created))
        specialties.append(dict(provider_key=key, specialty_code=practice["specialty"], is_primary=1))
        profiles[key] = dict(start=start, end=end, weight=weight, county=practice["county"],
                             specialty=practice["specialty"])

    # Some providers practice in two specialties (double-count trap).
    spec_codes = [code for code, _, _ in C.SPECIALTIES]
    for p in rng.sample(providers[: n_providers - n_never_referred], n_multi_specialty):
        second = rng.choice([s for s in spec_codes if s != p["primary_specialty"]])
        specialties.append(dict(provider_key=p["provider_key"], specialty_code=second, is_primary=0))

    specialty_dim = [dict(specialty_code=c, specialty_label=l) for c, l, _ in C.SPECIALTIES]
    return providers, specialties, specialty_dim, profiles
