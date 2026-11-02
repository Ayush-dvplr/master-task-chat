"""Rating, proration and settlement for the tariff engine.

Every amount is carried as an exact :class:`fractions.Fraction` of the decimal
values written in the input files and is only rounded, half to even, when a
line amount, a total or a credit is formed.
"""
import calendar
from datetime import date, timedelta
from fractions import Fraction


def round_money(value):
    """Return ``value`` rounded half to even to 0.01."""
    return Fraction(round(value * 100), 100)


def money(value):
    """Return an amount already rounded to 0.01 as a two-decimal string."""
    cents = round(value * 100)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def rate_tiers(quantity, tiers, offset=0):
    """Split the units of one meter across the plan tiers.

    ``offset`` is the number of the account's units that lie before this meter,
    so the split follows account positions rather than meter positions.
    Returns (tier number, units, rate) for every tier that receives units.
    """
    rated = []
    low = 0
    top = offset + quantity
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        high = top if cap is None else min(top, cap)
        units = high - max(offset, low)
        if units > 0:
            rated.append((number, units, tier["rate"]))
        if cap is None or top <= cap:
            break
        low = cap
    return rated


def energy_lines(meter, quantity, plan, offset=0):
    """Energy lines of a meter, their amount still the exact value."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "amount": units * Fraction(rate)}
        for number, units, rate in rate_tiers(quantity, plan["tiers"], offset)
    ]


def month_spans(start, end):
    """Yield (days in the calendar month, active days of it) from start to end."""
    cursor = start
    while cursor <= end:
        length = calendar.monthrange(cursor.year, cursor.month)[1]
        last = date(cursor.year, cursor.month, length)
        stop = min(last, end)
        yield length, (stop - cursor).days + 1
        cursor = last + timedelta(days=1)


def standing_line(meter, plan, start, end):
    """Standing line of a meter, prorated over each calendar month it touches."""
    charge = Fraction(plan["standing_charge"])
    value = Fraction(0)
    days = 0
    for length, active in month_spans(start, end):
        value += charge * active / length
        days += active
    return {"meter": meter, "kind": "standing", "tier": 0, "units": days,
            "amount": value}


def share_allowance(lines, allowance):
    """Return the allowance each line takes, in line order.

    The allowance is offered in equal parts to the account's energy lines, no
    line taking more than its exact value; whatever stays unshared is offered
    again to the lines that are not yet at zero, until none stays unshared or
    no such line is left.
    """
    shares = [Fraction(0)] * len(lines)
    energy = [index for index, line in enumerate(lines) if line["kind"] == "energy"]
    left = Fraction(allowance)
    room = {index: lines[index]["amount"] for index in energy}
    takers = energy
    while left > 0 and takers:
        part = left / len(takers)
        for index in takers:
            take = min(part, room[index])
            if take > 0:
                shares[index] += take
                room[index] -= take
                left -= take
        takers = [index for index in energy if room[index] > 0]
    return shares


def settle(lines, plan, commitment):
    """Return (subtotal, credit, total) for an invoice from its rounded lines."""
    subtotal = sum((line["amount"] for line in lines), Fraction(0))
    if subtotal >= Fraction(commitment):
        total = round_money(subtotal * (1 - Fraction(plan["credit_rate"])))
        credit = subtotal - total
    else:
        credit = Fraction(0)
        total = subtotal
    return subtotal, credit, total
