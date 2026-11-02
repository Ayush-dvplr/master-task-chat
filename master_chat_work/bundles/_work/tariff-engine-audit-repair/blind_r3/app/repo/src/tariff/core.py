"""Rating, proration and settlement for the tariff engine.

Every value is exact: rates and charges come in as ``Fraction`` built from the
decimals as written in the input files, and only line amounts and totals are
rounded half to even to 0.01.
"""
import calendar
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction


def exact(value):
    """Return a JSON number or decimal text as an exact Fraction."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, Decimal)):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(Decimal(repr(value)))
    return Fraction(Decimal(str(value).strip()))


def cents(value):
    """Round an exact value half to even to whole cents."""
    return round(Fraction(value) * 100)


def money(value_cents):
    """Write integer cents as an amount string with two decimals."""
    sign = "-" if value_cents < 0 else ""
    whole, part = divmod(abs(value_cents), 100)
    return f"{sign}{whole}.{part:02d}"


def rate_tiers(start, quantity, tiers):
    """Split a meter's units across the tiers by account position.

    ``start`` is the number of account units before this meter, so the meter's
    units hold positions start+1 .. start+quantity. Returns (tier number,
    units, rate) for every tier that covers some of them.
    """
    rated = []
    first, last = start + 1, start + quantity
    lower = 0
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        low = max(first, lower + 1)
        high = last if cap is None else min(last, int(cap))
        if high >= low:
            rated.append((number, high - low + 1, exact(tier["rate"])))
        if cap is None:
            break
        lower = int(cap)
    return rated


def energy_lines(meter, start, quantity, tiers):
    """Energy lines of a meter with their exact values (key ``exact``)."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "exact": units * rate}
        for number, units, rate in rate_tiers(start, quantity, tiers)
    ]


def standing_charge(plan, day):
    """Standing charge of ``day``: latest standing change on or before it."""
    charge = exact(plan["standing_charge"])
    latest = None
    for change in plan.get("standing_changes") or []:
        since = change["from"].strip() if isinstance(change["from"], str) else change["from"]
        if since <= day.isoformat() and (latest is None or since >= latest):
            latest = since
            charge = exact(change["standing_charge"])
    return charge


def standing_line(meter, plan, days):
    """Standing line over the active ``days``, each day prorated by its month."""
    value = Fraction(0)
    for day in days:
        value += standing_charge(plan, day) / calendar.monthrange(day.year, day.month)[1]
    return {"meter": meter, "kind": "standing", "tier": 0, "units": len(days),
            "exact": value}


def days_between(start, end):
    """Every day from ``start`` to ``end`` inclusive."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def share_allowance(lines, allowance):
    """Share ``allowance`` over the energy lines; return the unshared rest.

    Each energy line gets an ``share`` key: equal parts, never above its exact
    value, re-shared among lines not yet at zero while some stays unshared.
    """
    energy = [line for line in lines if line["kind"] == "energy"]
    for line in energy:
        line["share"] = Fraction(0)
    left = Fraction(allowance)
    while left > 0:
        open_lines = [line for line in energy if line["exact"] - line["share"] > 0]
        if not open_lines:
            break
        part = left / len(open_lines)
        for line in open_lines:
            take = min(part, line["exact"] - line["share"])
            line["share"] += take
            left -= take
    return left


def settle(lines, plan, commitment, credit_allowed=True):
    """Round the lines and return (subtotal, credit, total) in cents."""
    for line in lines:
        line["amount"] = money(cents(line["exact"] - line.get("share", 0)))
    subtotal = sum(cents(line["exact"] - line.get("share", 0)) for line in lines)
    credit = 0
    total = subtotal
    if credit_allowed and Fraction(subtotal, 100) >= exact(commitment):
        total = cents(Fraction(subtotal, 100) * (1 - exact(plan["credit_rate"])))
        credit = subtotal - total
    return subtotal, credit, total
