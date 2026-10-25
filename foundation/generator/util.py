"""Seeded random streams and calendar helpers (standard library only)."""
import hashlib
import math
import random
from datetime import date, datetime, time, timedelta

from .config import HOLIDAYS, SEED


def stream(name: str) -> random.Random:
    """Independent, reproducible random stream per table family.

    Each family gets its own generator derived from the master seed, so adding a
    new table later never shifts the rows of an existing one.
    """
    digest = hashlib.sha256(f"{SEED}:{name}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def weighted(rng: random.Random, pairs):
    """Pick a key from [(key, weight), ...] or {key: weight}."""
    items = list(pairs.items()) if isinstance(pairs, dict) else list(pairs)
    keys = [k for k, _ in items]
    weights = [w for _, w in items]
    return rng.choices(keys, weights=weights, k=1)[0]


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method; fine for the small rates used here."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def next_business_day(d: date) -> date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def add_business_days(d: date, n: int) -> date:
    d = next_business_day(d)
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining:
        d += timedelta(days=step)
        if is_business_day(d):
            remaining -= 1
    return d


def business_days_between(start: date, end: date):
    d = start
    while d <= end:
        if is_business_day(d):
            yield d
        d += timedelta(days=1)


def at(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour, minute))


def office_time(rng: random.Random, d: date, start_hour=8, end_hour=17) -> datetime:
    minutes = rng.randrange(start_hour * 60, end_hour * 60)
    return at(d, minutes // 60, minutes % 60)


def slot_time(rng: random.Random, d: date) -> datetime:
    """Chair appointments start on the half hour between 08:00 and 16:00."""
    slot = rng.randrange(0, 17)
    return at(d, 8 + slot // 2, 30 * (slot % 2))


def _nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def eastern_utc_offset_hours(d: date) -> int:
    """US Eastern: UTC-4 from the 2nd Sunday of March to the 1st Sunday of November."""
    dst_start = _nth_sunday(d.year, 3, 2)
    dst_end = _nth_sunday(d.year, 11, 1)
    return -4 if dst_start <= d < dst_end else -5


def to_utc(local: datetime) -> datetime:
    return local - timedelta(hours=eastern_utc_offset_hours(local.date()))


def fmt(value):
    """Serialize a value for CSV output."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())
