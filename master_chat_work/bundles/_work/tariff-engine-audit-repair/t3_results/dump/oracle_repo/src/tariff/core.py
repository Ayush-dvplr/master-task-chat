"""Rating, proration, allowance sharing and settlement for the tariff engine.

Every figure is an exact fraction built from the values as written in the
input files; each line is rounded half to even to 0.01 once.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction


def money(value):
    """Round an exact amount half to even to 0.01 and return it as a Decimal."""
    whole, rest = divmod(Fraction(value) * 100, 1)
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2):
        whole += 1
    return Decimal(int(whole)).scaleb(-2)


def rate_tiers(position, quantity, tiers):
    """Split a meter's units across the plan tiers by account position.

    The meter's units take the positions after ``position`` units of the
    meters before it.  Tier n covers the positions above the previous
    ``up_to`` up to and including its own.  Returns (tier number, units, rate)
    for every tier that covers some of the meter's units.
    """
    rated = []
    first, last = position + 1, position + quantity
    floor = 0
    for number, tier in enumerate(tiers, start=1):
        cap = None if tier["up_to"] is None else int(tier["up_to"])
        low = max(first, floor + 1)
        high = last if cap is None else min(last, cap)
        if high >= low:
            rated.append((number, high - low + 1, tier["rate"]))
        if cap is None or last <= cap:
            break
        floor = cap
    return rated


def energy_lines(meter, position, quantity, plan):
    """Energy lines of a meter with their exact values (before any allowance)."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "exact": units * Fraction(rate)}
        for number, units, rate in rate_tiers(position, quantity, plan["tiers"])
    ]


def standing_charge(plan, day):
    """The standing charge of ``day``: the standing_changes entry with the latest
    ``from`` on or before it, else the plan's own standing_charge."""
    found = None
    for change in plan.get("standing_changes", []):
        since = date.fromisoformat(str(change["from"]).strip())
        if since <= day and (found is None or since > found[0]):
            found = (since, change["standing_charge"])
    return Fraction(plan["standing_charge"] if found is None else found[1])


def standing_line(meter, plan, spans):
    """Standing line over the active day ranges ``spans`` of the billing period.

    Each active day adds the standing charge of that day / the days of its
    calendar month.
    """
    exact = Fraction(0)
    units = 0
    for first, last in spans:
        day = first
        while day <= last:
            length = calendar.monthrange(day.year, day.month)[1]
            exact += standing_charge(plan, day) / length
            units += 1
            day += timedelta(days=1)
    return {"meter": meter, "kind": "standing", "tier": 0, "units": units, "exact": exact}


def share_allowance(lines, allowance):
    """Take the allowance off the invoice's energy lines and return what no line can take.

    Every energy line first takes an equal part, never more than its exact
    value; what stays unshared is shared again in equal parts among the energy
    lines not yet at zero until none stays or no such line remains.
    """
    live = [line for line in lines if line["kind"] == "energy"]
    left = Fraction(allowance)
    while left > 0 and live:
        part = left / len(live)
        for line in live:
            take = min(part, line["exact"])
            line["exact"] -= take
            left -= take
        live = [line for line in live if line["exact"] > 0]
    return left


def settle(lines, plan, commitment, owed=False):
    """Return (subtotal, credit, total) for an invoice.

    The commitment credit is computed on the sum of the accepted, rated,
    prorated line amounts; the total is rounded once and the credit is the
    difference.  An invoice whose account still owes on its previous invoice
    (``owed``) gets no credit.
    """
    subtotal = sum((line["amount"] for line in lines), Decimal("0.00"))
    if subtotal >= commitment and not owed:
        total = money(Fraction(subtotal) * (1 - Fraction(plan["credit_rate"])))
    else:
        total = subtotal
    return subtotal, subtotal - total, total
