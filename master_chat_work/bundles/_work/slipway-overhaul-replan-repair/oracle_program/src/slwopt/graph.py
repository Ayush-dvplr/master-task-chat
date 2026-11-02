"""Stage p02. The precedence graph and the indexes the cascade walks.

An edge journal row is a lodgement, not a prerequisite. A row becomes a
prerequisite only once it has survived the crosswalk, the status test, the
kind test, the self test, the precinct test and the duplicate test. Two rows
that name the same pair after the crosswalk are one prerequisite.
"""
from . import reading

REJECTIONS = ["EDG-WITHDRAWN", "EDG-ADVISORY", "EDG-SELF", "EDG-UNKNOWNJOB",
              "EDG-CROSSPRECINCT", "EDG-DUPLICATE"]


def journal(root, alias):
    """Every lodgement, with both ends put through the crosswalk."""
    out = {}
    for row in reading.delimited(root / "precedence_edge_journal.psv",
                                 reading.PIPE):
        out[row["edge_id"]] = {
            "requiring_job": alias.get(row["requiring_job"], row["requiring_job"]),
            "required_job": alias.get(row["required_job"], row["required_job"]),
            "kind": row["kind"], "status": row["status"]}
    return out


def sift(rows, jobs):
    """Accepted prerequisite lists and one rejection row per lodgement the
    papers turn down."""
    accepted = {}
    rejected = []
    seen = set()
    for edge_id in sorted(rows):
        row = rows[edge_id]
        requiring = row["requiring_job"]
        required = row["required_job"]
        trail = (edge_id, requiring, required)
        if row["status"] != "active":
            rejected.append(trail + ("EDG-WITHDRAWN",))
        elif row["kind"] != "hard":
            rejected.append(trail + ("EDG-ADVISORY",))
        elif requiring == required:
            rejected.append(trail + ("EDG-SELF",))
        elif requiring not in jobs or required not in jobs:
            rejected.append(trail + ("EDG-UNKNOWNJOB",))
        elif jobs[requiring]["precinct"] != jobs[required]["precinct"]:
            rejected.append(trail + ("EDG-CROSSPRECINCT",))
        elif (requiring, required) in seen:
            rejected.append(trail + ("EDG-DUPLICATE",))
        else:
            seen.add((requiring, required))
            accepted.setdefault(requiring, []).append(required)
    for requiring in accepted:
        accepted[requiring].sort()
    return accepted, rejected


def within(rows, jobs, precinct):
    """The accepted prerequisite lists of one precinct on their own."""
    accepted = {}
    seen = set()
    for edge_id in sorted(rows):
        row = rows[edge_id]
        requiring = row["requiring_job"]
        required = row["required_job"]
        if requiring not in jobs or jobs[requiring]["precinct"] != precinct:
            continue
        if row["status"] != "active" or row["kind"] != "hard":
            continue
        if requiring == required or required not in jobs:
            continue
        if jobs[required]["precinct"] != precinct:
            continue
        if (requiring, required) in seen:
            continue
        seen.add((requiring, required))
        accepted.setdefault(requiring, []).append(required)
    for requiring in accepted:
        accepted[requiring].sort()
    return accepted


def stands_behind(accepted, start, target):
    """Whether the target stands among the prerequisites of the start job."""
    walk = [start]
    seen = set()
    while walk:
        here = walk.pop()
        if here == target and here != start:
            return True
        if here in seen:
            continue
        seen.add(here)
        for step in accepted.get(here, []):
            if step == target:
                return True
            walk.append(step)
    return False


def depths(accepted, names):
    """Longest chain below each job, so a cascade reaches a prerequisite
    before the job that names it."""
    out = {}

    def walk(name, active):
        if name in out:
            return out[name]
        if name in active:
            return 0
        active = active | {name}
        best = 0
        for step in accepted.get(name, []):
            best = max(best, 1 + walk(step, active))
        out[name] = best
        return best

    for name in names:
        walk(name, frozenset())
    return out


def in_a_cycle(accepted, names):
    return sorted(name for name in names
                  if stands_behind(accepted, name, name)
                  or name in accepted.get(name, []))


def reverse(accepted):
    out = {}
    for requiring in sorted(accepted):
        for required in accepted[requiring]:
            out.setdefault(required, []).append(requiring)
    return {k: sorted(v) for k, v in out.items()}


def readers_of(accepted, name, jobs, precinct):
    """Every job of this precinct whose closure holds this one."""
    out = set()
    for other in jobs:
        if jobs[other]["precinct"] != precinct or other == name:
            continue
        if stands_behind(accepted, other, name):
            out.add(other)
    return out


def groups(root, jobs):
    """Stage p08. Open memberships, with a job standing in two open groups
    kept by the group of the lower precedence number."""
    rows = [row for row in reading.delimited(root / "exclusive_slot_groups.csv")
            if row["state"] == "open" and row["member_job"] in jobs]
    owner = {}
    for row in sorted(rows, key=lambda r: (int(r["precedence"]), r["group_id"],
                                           r["member_job"])):
        owner.setdefault(row["member_job"], row["group_id"])
    held = {}
    rejected = []
    for row in sorted(rows, key=lambda r: (r["group_id"], r["member_job"])):
        if owner[row["member_job"]] != row["group_id"]:
            rejected.append((row["group_id"], row["member_job"],
                             "GRP-DOUBLEBOOKED"))
            continue
        entry = held.setdefault(row["group_id"],
                                {"group_id": row["group_id"],
                                 "precinct": row["precinct"],
                                 "precedence": int(row["precedence"]),
                                 "members": []})
        entry["members"].append(row["member_job"])
    for entry in held.values():
        entry["members"].sort()
    return held, rejected
