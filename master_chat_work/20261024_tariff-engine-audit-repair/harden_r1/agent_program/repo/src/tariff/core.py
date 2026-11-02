"""Rating, proration and settlement for the tariff engine."""
from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")


def money(value):
    """Return ``value`` rounded half to even to 0.01, as a two-decimal string."""
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_EVEN))


def rate_tiers(quantity, tiers):
    """Split a period quantity across the plan tiers.

    Tier 1 covers the quantity from 0 up to and including its ``up_to``; every
    later tier covers the quantity above the previous ``up_to`` up to and
    including its own, and an ``up_to`` of ``None`` has no upper end. Returns
    (tier number, units, rate) for every tier that covers at least one unit.
    """
    rated = []
    floor = 0
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        top = quantity if cap is None else min(quantity, cap)
        if top > floor:
            rated.append((number, top - floor, tier["rate"]))
        if cap is None or quantity <= cap:
            break
        floor = cap
    return rated


def energy_lines(meter, quantity, plan):
    """Return the energy lines of a meter, by tier number."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "amount": money(units * Decimal(rate))}
        for number, units, rate in rate_tiers(quantity, plan["tiers"])
    ]


def standing_line(meter, plan, active_days, month_days):
    """Standing charge of a meter, prorated over the days of the month."""
    exact = Decimal(plan["standing_charge"]) * active_days / month_days
    return {"meter": meter, "kind": "standing", "tier": 0, "units": active_days,
            "amount": money(exact)}


def settle(lines, plan, commitment):
    """Return (subtotal, credit, total) for an invoice as two-decimal strings.

    The subtotal is the sum of the line amounts; the commitment credit applies
    once the subtotal reaches the commitment.
    """
    subtotal = sum((Decimal(line["amount"]) for line in lines), Decimal(0))
    if subtotal >= commitment:
        total = Decimal(money(subtotal * (Decimal(1) - Decimal(plan["credit_rate"]))))
        credit = subtotal - total
    else:
        credit = Decimal(0)
        total = subtotal
    return money(subtotal), money(credit), money(total)
