"""Pieces of the data product config compiler, implemented from SPEC.md."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

PASS = object()

_TS = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?"
    r"(?:([Zz])|([+-])(\d{2}):(\d{2}))$"
)


def _canon(product_id: str) -> str:
    return product_id.upper().replace("-", "")


def event_date(line: str) -> str:
    """UTC calendar date (YYYY-MM-DD) of the instant named by the line's RFC 3339 timestamp."""
    stamp = line.split()[0]
    m = _TS.match(stamp)
    if m is None:
        raise ValueError(f"bad RFC 3339 timestamp: {stamp!r}")
    year, month, day, hour, minute, second = (int(g) for g in m.groups()[:6])
    second = min(second, 59)  # a leap second 23:59:60 still falls on that same date
    local = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    if m.group(8):
        offset = timedelta(hours=int(m.group(9)), minutes=int(m.group(10)))
        if m.group(8) == "-":
            offset = -offset
        local -= offset
    return local.date().isoformat()


def retire_events(lines: list[str]) -> tuple[dict, dict]:
    """Earliest RETIRE date per canonical product id and per owner."""
    products: dict[str, str] = {}
    owners: dict[str, str] = {}
    for line in lines:
        tokens = line.split()
        if len(tokens) < 2 or tokens[1] != "RETIRE":
            continue
        day = event_date(line)
        for token in tokens[2:]:
            key, sep, value = token.partition("=")
            if not sep or not value:
                continue
            if key == "product":
                target, name = products, _canon(value)
            elif key == "owner":
                target, name = owners, value
            else:
                continue
            if name not in target or day < target[name]:
                target[name] = day
    return products, owners


def assignment(rows: list[dict], owner: str, d: str) -> dict | None:
    """The owner's row with the latest active_from on or before d."""
    best = None
    for row in rows:
        if row["owner"] != owner or row["active_from"] > d:
            continue
        if best is None or row["active_from"] > best["active_from"]:
            best = row
    return best


def owner_team(rows, retired_owners: dict, owner: str, d: str) -> str | None:
    """The owner's team on d if the owner is an active owner on d, else None."""
    row = assignment(rows, owner, d)
    if row is None:
        return None
    active_to = row["active_to"]
    if active_to and active_to < d:
        return None
    if owner in retired_owners and retired_owners[owner] <= d:
        return None
    return row["team"]


def read_text(type_: str, text: str):
    """Read one text-layer value by schema type; PASS when it does not read as that type."""
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    if type_ == "integer":
        return int(text) if re.fullmatch(r"[0-9]+", text) else PASS
    if type_ == "boolean":
        lowered = text.lower()
        return {"true": True, "false": False}.get(lowered, PASS)
    if type_ in ("enum", "string"):
        return text
    if type_ == "list":
        if text == "":
            return []
        return [item.strip(" ") for item in text.split(",")]
    raise ValueError(f"unknown schema type: {type_!r}")


def _largest_remainder(q: int, weights: dict[str, int]) -> dict[str, int]:
    """Hand out q units in proportion to weight: floors first, then by largest remainder."""
    total = sum(weights.values())
    if q <= 0 or total <= 0:
        return {pid: 0 for pid in weights}
    shares = {pid: q * w // total for pid, w in weights.items()}
    left = q - sum(shares.values())
    order = sorted(weights, key=lambda pid: (-(q * weights[pid] % total), pid))
    for pid in order[:left]:
        shares[pid] += 1
    return shares


def split_quota(q: int, products: dict[str, tuple[int, int | None]]) -> dict[str, int]:
    """Divide quota q over the active products, honouring quota_cap with repeated redistribution."""
    weights = {pid: w for pid, (w, _cap) in products.items()}
    caps = {pid: cap for pid, (_w, cap) in products.items()}
    units = _largest_remainder(q, weights)
    while True:
        given_back = 0
        for pid, cap in caps.items():
            if cap is not None and units[pid] > cap:
                given_back += units[pid] - cap
                units[pid] = cap
        if given_back == 0:
            return units
        eligible = {
            pid: weights[pid]
            for pid, cap in caps.items()
            if cap is None or units[pid] < cap
        }
        extra = _largest_remainder(given_back, eligible)
        if not any(extra.values()):
            return units
        for pid, n in extra.items():
            units[pid] += n
