"""Rating, proration and settlement for the tariff engine.

All arithmetic is exact (``fractions.Fraction`` built from the decimal values as
written in the input files); amounts are rounded half to even to whole cents
only where the contract says so.
"""
import calendar
from datetime import date
from decimal import Decimal
from fractions import Fraction


def exact(value):
    """Exact Fraction of an int, Decimal or decimal text (never a binary float)."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, Decimal)):
        return Fraction(value)
    return Fraction(Decimal(str(value).strip()))


def cents(value):
    """Round an exact value half to even to an integer number of cents."""
    return round(exact(value) * 100)


def money(amount_cents):
    """Format integer cents as a string with exactly two decimals."""
    sign = "-" if amount_cents < 0 else ""
    whole, part = divmod(abs(amount_cents), 100)
    return f"{sign}{whole}.{part:02d}"


def rate_tiers(quantities, tiers):
    """Split an account's period quantities across the plan tiers.

    ``quantities`` is a list of (meter, period quantity) in ascending meter
    order; units take account positions from 1 in that order. Tier 1 covers
    positions 1..up_to, each later tier the positions above the previous
    ``up_to`` up to its own, and a ``None`` tier has no upper end. Returns
    {meter: [(tier number, units, rate), ...]} for the tiers covering units.
    """
    rated = {}
    offset = 0
    for meter, quantity in quantities:
        first, last = offset + 1, offset + quantity
        lines = []
        floor = 0
        for number, tier in enumerate(tiers, start=1):
            cap = tier["up_to"]
            low = max(first, floor + 1)
            high = last if cap is None else min(last, cap)
            if high >= low:
                lines.append((number, high - low + 1, tier["rate"]))
            if cap is None:
                break
            floor = cap
        rated[meter] = lines
        offset = last
    return rated


def energy_lines(meter, rated):
    """Energy lines of a meter with their exact (unshared) values."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "exact": units * exact(rate)}
        for number, units, rate in rated
    ]


def standing_charge_on(plan, day):
    """Standing charge of a day: latest ``standing_changes`` entry on or before it."""
    charge = plan["standing_charge"]
    latest = None
    for change in plan.get("standing_changes") or []:
        start = change["from"]
        if not isinstance(start, date):
            start = date.fromisoformat(str(start).strip())
        if start <= day and (latest is None or start >= latest):
            latest = start
            charge = change["standing_charge"]
    return exact(charge)


def standing_line(meter, plan, active_days):
    """Standing line of a meter over its list of active days (dates)."""
    value = Fraction(0)
    for day in active_days:
        value += standing_charge_on(plan, day) / calendar.monthrange(day.year, day.month)[1]
    return {"meter": meter, "kind": "standing", "tier": 0, "units": len(active_days),
            "exact": value}


def share_allowance(lines, allowance):
    """Share the allowance over the energy lines in equal parts.

    Each energy line takes an equal part but never more than its remaining
    exact value; what is left is shared again among the lines not yet at zero
    until nothing is left or no such line remains. Sets ``share`` on every
    energy line and returns the allowance no line could take.
    """
    energy = [line for line in lines if line["kind"] == "energy"]
    for line in energy:
        line["share"] = Fraction(0)
    left = exact(allowance)
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


def line_cents(line):
    """Line amount in cents: exact value less energy share, rounded half to even."""
    return cents(line["exact"] - line.get("share", 0))


def settle(subtotal_cents, plan, commitment, eligible=True):
    """Return (subtotal, credit, total) in cents for an invoice.

    When the invoice is eligible and its subtotal is at least the commitment,
    total = subtotal x (1 - credit_rate) rounded half to even and credit is
    subtotal minus total; otherwise credit is 0 and total is the subtotal.
    """
    if eligible and Fraction(subtotal_cents, 100) >= exact(commitment):
        total = cents(Fraction(subtotal_cents, 100) * (1 - exact(plan["credit_rate"])))
        return subtotal_cents, subtotal_cents - total, total
    return subtotal_cents, 0, subtotal_cents
