"""Rating, proration and settlement for the tariff engine."""
from calendar import monthrange
from datetime import date
from decimal import Decimal
from fractions import Fraction


def exact(value):
    """The value as written in the input file, as an exact fraction."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Fraction(value)
    return Fraction(Decimal(str(value).strip()))


def round_cents(value):
    """Round an exact value half to even to 0.01 and return it in cents."""
    return round(exact(value) * 100)


def money(cents):
    """Write an amount held in cents with exactly two decimals."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def rate_tiers(offset, quantity, tiers):
    """Split the units of one meter across the plan tiers.

    ``offset`` is the number of the account's units billed before this meter,
    so the meter holds the account positions ``offset + 1`` to
    ``offset + quantity``. Tier 1 covers the positions up to and including its
    ``up_to``, every later tier the positions above the previous ``up_to``.
    Returns (tier number, units, rate) for every tier that receives units.
    """
    rated = []
    lower = 0
    for number, tier in enumerate(tiers, start=1):
        cap = tier["up_to"]
        bottom = max(offset, lower)
        top = offset + quantity if cap is None else min(offset + quantity, cap)
        if top > bottom:
            rated.append((number, top - bottom, tier["rate"]))
        if cap is None or offset + quantity <= cap:
            break
        lower = cap
    return rated


def energy_lines(meter, offset, quantity, tiers):
    """The energy lines of one meter, in tier order, with their exact values."""
    return [
        {"meter": meter, "kind": "energy", "tier": number, "units": units,
         "exact": units * exact(rate)}
        for number, units, rate in rate_tiers(offset, quantity, tiers)
    ]


def standing_charge(plan, day):
    """The standing charge of the plan on one day."""
    charge = plan["standing_charge"]
    latest = None
    for change in plan.get("standing_changes") or ():
        start = date.fromisoformat(str(change["from"]).strip())
        if start <= day and (latest is None or start > latest):
            latest, charge = start, change["standing_charge"]
    return exact(charge)


def standing_line(meter, plan, days):
    """The standing line of a meter over its active ``days``.

    Each day carries the standing charge of that day divided by the number of
    days in that day's month.
    """
    value = Fraction(0)
    for day in days:
        value += standing_charge(plan, day) / monthrange(day.year, day.month)[1]
    return {"meter": meter, "kind": "standing", "tier": 0, "units": len(days),
            "exact": value}


def share_allowance(values, allowance):
    """Share an allowance over the exact values of the energy lines.

    Every line takes an equal part of the allowance but never more than its
    exact value; what stays unshared is shared again among the lines that are
    not yet at zero. Returns (shares, unshared).
    """
    shares = [Fraction(0)] * len(values)
    pool = exact(allowance)
    while pool > 0:
        open_lines = [index for index in range(len(values))
                      if values[index] - shares[index] > 0]
        if not open_lines:
            break
        part = pool / len(open_lines)
        for index in open_lines:
            taken = min(part, values[index] - shares[index])
            shares[index] += taken
            pool -= taken
    return shares, pool


def settle(amounts, commitment, credit_rate, allow_credit=True):
    """Return (subtotal, credit, total) in cents for an invoice.

    The commitment credit applies when the subtotal of the invoice's rated and
    prorated lines reaches the commitment.
    """
    subtotal = sum(amounts)
    if allow_credit and subtotal >= commitment:
        total = round_cents(Fraction(subtotal, 100) * (1 - exact(credit_rate)))
        return subtotal, subtotal - total, total
    return subtotal, 0, subtotal


def redeem(balance, vouchers):
    """The vouchers adding up to the largest sum not above ``balance``.

    ``vouchers`` maps a voucher id to its amount in cents and ``balance`` is in
    cents. Returns (ids in ascending order, sum in cents); of the sets reaching
    that sum the one whose id list comes first is taken.
    """
    items = sorted(vouchers.items())
    mask = (1 << (min(balance, sum(vouchers.values())) + 1)) - 1
    reachable = [1] * (len(items) + 1)
    for index in range(len(items) - 1, -1, -1):
        rest = reachable[index + 1]
        reachable[index] = (rest | (rest << items[index][1])) & mask
    best = reachable[0].bit_length() - 1
    chosen = []
    left = best
    for index, (voucher, amount) in enumerate(items):
        if amount <= left and (reachable[index + 1] >> (left - amount)) & 1:
            chosen.append(voucher)
            left -= amount
    return chosen, best
