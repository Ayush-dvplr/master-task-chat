"""Rating, proration and settlement for the tariff engine."""


def rate_tiers(quantity, tiers):
    """Split a period quantity across the plan tiers.

    Returns (tier number, units, rate) for every tier that receives units.
    """
    rated = []
    floor = 0
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        top = quantity if cap is None else min(quantity, cap - 1)
        if top > floor:
            rated.append((number, top - floor, tier["rate"]))
        if cap is None or quantity < cap:
            break
        floor = cap - 1
    return rated


def energy_lines(meter, quantity, plan):
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "amount": units * rate}
        for number, units, rate in rate_tiers(quantity, plan["tiers"])
    ]


def standing_line(meter, plan, active_days):
    """Standing charge of a meter, prorated over a 30-day month."""
    return {"meter": meter, "kind": "standing", "tier": 0, "units": active_days,
            "amount": plan["standing_charge"] * active_days / 30}


def settle(lines, base, plan, commitment):
    """Return (subtotal, credit, total) for an invoice.

    ``base`` is the metered consumption charge of the account; the commitment
    credit applies once it reaches the commitment.
    """
    subtotal = sum(line["amount"] for line in lines)
    credit = 0.0
    if base >= commitment:
        credit = round(base * plan["credit_rate"], 2)
    total = round(subtotal - credit, 2)
    return subtotal, credit, total
