"""Overtime allowance settlement on a fixed plan (reference + slip modes for the kill test).
rows: scheduled checks as dicts with request_id, base, aircraft_class, start, due (day numbers), overtime_shifts.
grants: {base: allowance_shifts}. Returns per-check {id: allowance_shifts} and per-base/fleet overrides."""
RANK = {"widebody": 0, "narrowbody": 1, "regional": 2}
BASES = ["North", "South", "West", "East"]
MODES = ["ref", "granted_not_used", "cap_not_subtracted", "per_base_cap", "unordered", "tie_by_base",
         "start_first", "start_key", "whole_only"]


def order(rows, mode):
    if mode == "unordered":
        key = lambda r: r["request_id"]
    elif mode == "start_first":
        key = lambda r: (r["start"], RANK[r["aircraft_class"]], r["request_id"])
    elif mode == "start_key":
        key = lambda r: (RANK[r["aircraft_class"]], r["start"], r["request_id"])
    elif mode == "tie_by_base":
        key = lambda r: (RANK[r["aircraft_class"]], r["due"], BASES.index(r["base"]), r["request_id"])
    else:
        key = lambda r: (RANK[r["aircraft_class"]], r["due"], r["request_id"])
    return sorted(rows, key=key)


def settle(rows, grants, mode="ref"):
    """-> (take {request_id: allowance_shifts}, base_used override or None, subtract flag)"""
    take = {}
    if mode == "per_base_cap":
        left = dict(grants)
        for r in order(rows, "ref"):
            t = min(r["overtime_shifts"], left[r["base"]])
            left[r["base"]] -= t
            take[r["request_id"]] = t
        return take, None, True
    left = sum(grants.values())
    for r in order(rows, mode):
        h = r["overtime_shifts"]
        if mode == "whole_only":
            t = h if h <= left else 0
        else:
            t = min(h, left)
        left -= t
        take[r["request_id"]] = t
    over = dict(grants) if mode == "granted_not_used" else None
    return take, over, mode != "cap_not_subtracted"


def priority(rows):
    return order(rows, "ref")
