"""Instant, date and zone handling for warrant-ctl.

Every instant inside the compiler is an integer count of seconds since the
Unix epoch, UTC. Zone arithmetic uses the offline rule table shipped with the
corpus (tz_rules.json), never the host zone database.
"""

from __future__ import annotations

import bisect
import calendar
import re
from datetime import datetime, timezone

INF = 1 << 62

_INSTANT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_HHMM = re.compile(r"^(\d{2}):(\d{2})$")


class BadTime(ValueError):
    pass


def _civil(y: int, mo: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> int:
    try:
        datetime(y, mo, d, h, mi, s)
    except ValueError as exc:
        raise BadTime(str(exc)) from None
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def parse_instant(text) -> int:
    if not isinstance(text, str):
        raise BadTime(repr(text))
    m = _INSTANT.match(text)
    if not m:
        raise BadTime(text)
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    base = _civil(y, mo, d, h, mi, s)
    off = m.group(7)
    if off == "Z":
        return base
    oh, om = int(off[1:3]), int(off[4:6])
    if oh > 23 or om > 59:
        raise BadTime(text)
    delta = oh * 3600 + om * 60
    return base - delta if off[0] == "+" else base + delta


def parse_date(text) -> tuple[int, int, int]:
    if not isinstance(text, str):
        raise BadTime(repr(text))
    m = _DATE.match(text)
    if not m:
        raise BadTime(text)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    _civil(y, mo, d)
    return y, mo, d


def parse_epoch(text, scale: int = 1) -> int:
    """Integer epoch field; scale 1000 for milliseconds. Returns the raw integer."""
    if isinstance(text, bool):
        raise BadTime(repr(text))
    if isinstance(text, int):
        return text
    if isinstance(text, str) and text.isdigit():
        return int(text)
    raise BadTime(repr(text))


def fmt(ts: int) -> str:
    if ts >= INF:
        return "open"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Zone:
    def __init__(self, name: str, spec: dict) -> None:
        self.name = name
        self.std = int(spec["std_offset_min"]) * 60
        self.dst = int(spec.get("dst_offset_min", spec["std_offset_min"])) * 60
        pairs = sorted((parse_instant(at), kind) for at, kind in spec.get("transitions", []))
        self.points = [p for p, _ in pairs]
        self.kinds = [k for _, k in pairs]

    def offset_at(self, u: int) -> int:
        if not self.points:
            return self.std
        i = bisect.bisect_right(self.points, u) - 1
        if i < 0:
            kind = "std" if self.kinds[0] == "dst" else "dst"
        else:
            kind = self.kinds[i]
        return self.dst if kind == "dst" else self.std

    def to_utc(self, local: int) -> int:
        hits = [local - o for o in sorted({self.std, self.dst}) if self.offset_at(local - o) == o]
        if hits:
            return min(hits)
        return local - self.std


class Zones:
    def __init__(self, table: dict) -> None:
        self.by_name = {name: Zone(name, spec) for name, spec in table["zones"].items()}

    def get(self, name: str) -> Zone:
        return self.by_name[name]

    def local_midnight(self, zone: str, ymd: tuple[int, int, int]) -> int:
        y, mo, d = ymd
        return self.get(zone).to_utc(_civil(y, mo, d))

    def local_wall(self, zone: str, ymd: tuple[int, int, int], hhmm: str) -> int:
        m = _HHMM.match(hhmm)
        if not m:
            raise BadTime(hhmm)
        y, mo, d = ymd
        return self.get(zone).to_utc(_civil(y, mo, d, int(m.group(1)), int(m.group(2))))


def add_days(ymd: tuple[int, int, int], days: int) -> tuple[int, int, int]:
    t = _civil(*ymd) + days * 86400
    g = datetime.fromtimestamp(t, timezone.utc)
    return g.year, g.month, g.day


def weekday(ymd: tuple[int, int, int]) -> int:
    return datetime(*ymd).weekday()


def local_date_of(zones: Zones, zone: str, u: int) -> tuple[int, int, int]:
    off = zones.get(zone).offset_at(u)
    g = datetime.fromtimestamp(u + off, timezone.utc)
    return g.year, g.month, g.day
