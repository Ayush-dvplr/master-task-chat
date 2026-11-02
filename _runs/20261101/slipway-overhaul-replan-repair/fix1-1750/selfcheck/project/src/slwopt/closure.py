"""Stages p05 and p06. The closure layer and the demand layer.

The closure of a job is every job that stands behind it, however far back. A
job is blocked when it is inadmissible itself or when anything in its closure
is, and a blocked job is never selectable. The demand layer holds what a job
draws on its own and what the closed set it opens draws once each distinct
job is counted one time.
"""
from . import normalise

POOLS = normalise.POOLS


def closure_inputs(model, name, seen):
    behind = model.accepted.get(name, [])
    return [behind,
            [seen["closure|" + step]["digest"] for step in behind
             if "closure|" + step in seen],
            seen["norm|" + name]["digest"]]


def closure(model, name, seen):
    walk = list(model.accepted.get(name, []))
    reached = set()
    missing = False
    while walk:
        here = walk.pop()
        if here in reached or here == name:
            continue
        if here not in model.jobs:
            missing = True
            continue
        reached.add(here)
        walk.extend(model.accepted.get(here, []))
    own = seen["norm|" + name]["value"]
    blocked = False
    reason = ""
    if not own["admissible"]:
        blocked = True
        reason = own["admission_reason"]
    elif missing or any(not seen["norm|" + step]["value"]["admissible"]
                        for step in reached):
        blocked = True
        reason = "JOB-CLOSUREBLOCKED"
    return {"job_id": name, "closure": sorted(reached), "blocked": blocked,
            "reason": reason}


def demand_inputs(model, name, seen):
    held = seen["closure|" + name]
    members = sorted(set([name] + list(held["value"]["closure"])))
    return [held["digest"], [seen["norm|" + m]["digest"] for m in members]]


def demand(model, name, seen):
    own = seen["norm|" + name]["value"]
    members = sorted(set([name] + list(seen["closure|" + name]["value"]["closure"])))
    closed = {}
    for pool in POOLS:
        closed[pool] = sum(seen["norm|" + m]["value"][pool] for m in members)
    return {"job_id": name, "own": {pool: own[pool] for pool in POOLS},
            "closed": closed}
