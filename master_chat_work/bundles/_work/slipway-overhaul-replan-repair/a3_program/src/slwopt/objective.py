"""Stage p10. What one accepted set costs and how two of them are ranked.

The class multiplier reaches the base charge first. The surcharges of the
precinct are added next. The closure rebate is taken last, over the scaled
charges and the surcharges together. A charter job that is admissible, is not
blocked and is left out of the closed set carries its deferral penalty; a job
that could not be taken carries none.
"""
from fractions import Fraction

from . import normalise

POOLS = normalise.POOLS


def usage_of(closed, own):
    return {pool: sum(own[name][pool] for name in closed) for pool in POOLS}


def within_capacity(usage, available):
    """A usage equal to the available quantity is within the pool."""
    for pool in POOLS:
        if usage[pool] > available[pool]:
            return False
    return True


def surcharge_of(closed, rules, usage, norms):
    total = 0
    for rule in rules:
        if rule["kind"] == "pair_surcharge":
            if rule["first_job"] in closed and rule["second_job"] in closed:
                total += rule["amount_mills"]
        elif rule["kind"] == "threshold_surcharge":
            if usage[rule["pool"]] > rule["threshold"]:
                total += rule["amount_mills"] * sum(
                    1 for name in closed
                    if norms[name]["class"] == rule["class"])
    return total


def rebate_of(closed, rules, closures, over):
    total = 0
    for rule in rules:
        if rule["kind"] != "closure_rebate":
            continue
        anchor = rule["anchor_job"]
        if anchor in closed and len(closures.get(anchor, [])) >= 2:
            total += normalise.half_up(Fraction(over * rule["rebate_bp"], 10000))
    return total


def weighted_of(usage, weights):
    total = Fraction(0)
    for pool in POOLS:
        top, bottom = weights[pool]
        total += Fraction(top, bottom) * usage[pool]
    return total


def ranking(total, weighted, optional, closed):
    """The lexicographic key: charge, then weighted resource, then the count
    of optional jobs taken, then the canonical job order."""
    return (total, weighted, optional, list(closed))
