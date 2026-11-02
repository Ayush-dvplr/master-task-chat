"""Rating, proration and settlement for the tariff engine.

Every value is held as an exact ``fractions.Fraction`` built from the decimal
text written in the input files; amounts are rounded half to even to 0.01 only
where the contract rounds them.
"""
import calendar
from decimal import Decimal
from fractions import Fraction

CENT = Fraction(1, 100)


def exact(value):
    """Return ``value`` (int, Decimal, str or Fraction) as an exact Fraction."""
    if isinstance(value, bool):
        raise TypeError("a boolean is not a number")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, Decimal)):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(Decimal(repr(value)))
    return Fraction(Decimal(str(value).strip()))


def round_cents(value):
    """Round an exact value half to even to 0.01."""
    return Fraction(round(exact(value) / CENT)) * CENT


def money(value):
    """Format an amount as a string with exactly two decimals."""
    cents = int(round_cents(value) / CENT)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def rate_tiers(quantity, tiers, offset=0):
    """Split ``quantity`` units across the plan tiers.

    The units take the account positions ``offset + 1`` to ``offset +
    quantity``. Tier 1 covers positions 1 to its ``up_to`` inclusive, every
    later tier the positions above the previous ``up_to`` up to and including
    its own, and a ``None`` cap has no upper end. Returns (tier number, units,
    rate) for every tier that covers some of the units.
    """
    rated = []
    low = offset + 1
    high = offset + quantity
    floor = 0
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        first = max(low, floor + 1)
        last = high if cap is None else min(high, cap)
        if last >= first:
            rated.append((number, last - first + 1, exact(tier["rate"])))
        if cap is None:
            break
        floor = cap
    return rated


def energy_lines(meter, quantity, plan, offset=0):
    """Energy lines of one meter; ``exact`` holds the unrounded value."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "exact": units * rate}
        for number, units, rate in rate_tiers(quantity, plan["tiers"], offset)
    ]


def charge_on(plan, day):
    """Standing charge of ``day``: latest change on or before it, else the plan's."""
    charge = plan["standing_charge"]
    latest = None
    for change in plan.get("standing_changes") or []:
        start = change["from"]
        if start <= day and (latest is None or start >= latest):
            latest = start
            charge = change["standing_charge"]
    return exact(charge)


def standing_line(meter, plan, active_days):
    """Standing line over the list of active days, or None without any.

    Each day costs the standing charge of that day divided by the number of
    days in its calendar month.
    """
    if not active_days:
        return None
    value = sum((charge_on(plan, day) / calendar.monthrange(day.year, day.month)[1]
                 for day in active_days), Fraction(0))
    return {"meter": meter, "kind": "standing", "tier": 0, "units": len(active_days),
            "exact": value}


def share_allowance(values, allowance):
    """Share ``allowance`` across energy values in equal parts.

    A line never takes more than its remaining exact value; what a line cannot
    take is shared again among the lines not yet at zero. Returns (shares,
    unshared allowance).
    """
    shares = [Fraction(0)] * len(values)
    left = exact(allowance)
    while left > 0:
        open_lines = [i for i, value in enumerate(values) if value - shares[i] > 0]
        if not open_lines:
            break
        part = left / len(open_lines)
        for i in open_lines:
            take = min(part, values[i] - shares[i])
            shares[i] += take
            left -= take
    return shares, left


def settle(lines, plan, commitment, allowance):
    """Apply the allowance, round the lines and settle the invoice.

    Returns (finished lines, subtotal, credit, total, unshared allowance);
    amounts are exact Fractions of whole cents.
    """
    energy = [i for i, line in enumerate(lines) if line["kind"] == "energy"]
    shares, left = share_allowance([lines[i]["exact"] for i in energy], allowance)
    share_of = dict(zip(energy, shares))
    finished = []
    subtotal = Fraction(0)
    for i, line in enumerate(lines):
        amount = round_cents(line["exact"] - share_of.get(i, Fraction(0)))
        subtotal += amount
        out = {key: value for key, value in line.items() if key != "exact"}
        out["amount"] = amount
        finished.append(out)
    if subtotal >= exact(commitment):
        total = round_cents(subtotal * (1 - exact(plan["credit_rate"])))
        credit = subtotal - total
    else:
        credit = Fraction(0)
        total = subtotal
    return finished, subtotal, credit, total, left
