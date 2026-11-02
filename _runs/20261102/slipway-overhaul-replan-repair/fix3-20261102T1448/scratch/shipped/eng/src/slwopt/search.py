"""Stages p09 and p11. The exact optimum of one precinct.

Every subset of the selectable jobs is examined in ascending mask order. A
subset is opened into its closed set, tested against the binding slot groups
and against the pool capacities, charged, and ranked. The lexicographic least
is kept.
"""
from . import normalise, objective

POOLS = normalise.POOLS


def available_of(model, precinct):
    out = {}
    for pool in POOLS:
        carried = sum(entry["quantity"] for entry in model.carryover.values()
                      if entry["precinct"] == precinct and entry["pool"] == pool)
        out[pool] = model.capacity.get((precinct, pool), 0) - carried
    return out


def solve_inputs(model, precinct, seen):
    names = model.in_precinct(precinct)
    groups = [g for g in sorted(model.groups)
              if model.groups[g]["precinct"] == precinct]
    rules = [r for r in sorted(model.rules)
             if model.rules[r]["precinct"] == precinct]
    available = available_of(model, precinct)
    return [[[pool, available[pool]] for pool in POOLS],
            [[seen["closure|" + n]["digest"], seen["demand|" + n]["digest"],
              seen["charge|" + n]["digest"]] for n in names],
            [seen["group|" + g]["digest"] for g in groups],
            [],
            [[pool, model.params["pool_weights"][pool][0],
              model.params["pool_weights"][pool][1]] for pool in POOLS]]


def sweep(model, precinct, seen):
    names = model.in_precinct(precinct)
    norms = {n: seen["norm|" + n]["value"] for n in names}
    closures = {n: seen["closure|" + n]["value"]["closure"] for n in names}
    blocked = {n: seen["closure|" + n]["value"]["blocked"] for n in names}
    own = {n: seen["demand|" + n]["value"]["own"] for n in names}
    charges = {n: seen["charge|" + n]["value"] for n in names}
    selectable = [n for n in names if not blocked[n]]
    groups = [seen["group|" + g]["value"] for g in sorted(model.groups)
              if model.groups[g]["precinct"] == precinct]
    binding = [g["members"] for g in groups if g["binding"]]
    rules = [seen["rule|" + r]["value"] for r in sorted(model.rules)
             if model.rules[r]["precinct"] == precinct]
    available = available_of(model, precinct)
    weights = model.params["pool_weights"]
    charter = [n for n in selectable if norms[n]["standing"] == "charter"]

    examined = 0
    by_group = 0
    by_capacity = 0
    feasible = 0
    best = None
    body = None
    width = len(selectable)
    for mask in range(1 << width):
        examined += 1
        chosen = [selectable[i] for i in range(width) if mask >> i & 1]
        opened = set(chosen)
        for name in chosen:
            opened.update(closures[name])
        closed = sorted(opened)
        clash = False
        for members in binding:
            if len(set(members) & set(closed)) > 1:
                clash = True
                break
        if clash:
            by_group += 1
            continue
        usage = objective.usage_of(closed, own)
        if not objective.within_capacity(usage, available):
            by_capacity += 1
            continue
        feasible += 1
        base = sum(charges[name]["scaled_charge_mills"] for name in closed)
        surcharge = objective.surcharge_of(closed, rules, usage, norms)
        rebate = objective.rebate_of(closed, rules, closures, base)
        penalty = sum(charges[name]["deferral_penalty_mills"]
                      for name in names if name not in closed)
        total = base + surcharge - rebate + penalty
        weighted = objective.weighted_of(usage, weights)
        optional = sum(1 for name in closed
                       if norms[name]["standing"] == "optional")
        key = objective.ranking(total, weighted, optional, closed)
        if best is None or key < best:
            best = key
            body = {"selected": list(chosen), "closed_set": closed,
                    "usage": usage, "base_mills": base,
                    "surcharge_mills": surcharge, "rebate_mills": rebate,
                    "penalty_mills": penalty, "total_mills": total,
                    "optional_count": optional,
                    "weighted_resource": normalise.ratio(weighted)}
    if body is None:
        raise SystemExit("precinct " + precinct + " admits no feasible set")
    return {"precinct": precinct, "selectable": selectable,
            "subsets_examined": examined, "subsets_group_rejected": by_group,
            "subsets_capacity_rejected": by_capacity,
            "subsets_feasible": feasible, "available": available, **body}
