"""Write the shipped sample and hidden prototype corpora.
Usage: gen_proto.py outroot shipped_seed "h_seed:empty[:traps[:stype]] ..."  e.g. gen_proto.py /tmp/c 2 "3:1::cap 5:0::bind"
stype: slack | cap | short | bind (allowance against the reference plan's overtime).
Shipped: n=5 per base. Hidden: n=8 per base; empty=1 adds one base with no eligible request and an empty segment."""
import json
import os
import sys

import random

from absgen import make
from ref import solve
from render import render
from settle import priority


def rows_of(inst, res):
    rows = []
    for c in inst["checks"]:
        s, f, x = res["plan"][c["id"]]
        h = inst["types"][c["type"]]["h"] * x
        if s <= inst["S"] and h:
            rows.append({"request_id": c["id"], "base": c["base"], "aircraft_class": c["cls"], "start": s,
                         "due": c["due"], "overtime_shifts": h})
    return rows


def plant_pair(inst, rows, g):
    """Give two overtime checks of one class at two bases the same due date, so the request_id tie decides
    their order; the smaller id sits at the later base. Re-solve and keep the first candidate whose plan still
    has both checks on overtime with the run-out point inside the first. -> (A, pair) or None"""
    import copy
    bi = inst["bases"].index
    cands = []
    for a in rows:
        for b in rows:
            if a["aircraft_class"] == b["aircraft_class"] and a["request_id"] < b["request_id"] \
                    and bi(a["base"]) > bi(b["base"]) and a["overtime_shifts"] >= 2:
                cands.append((a, b))
    g.shuffle(cands)
    for a, b in cands[:12]:
        trial = copy.deepcopy(inst)
        due = max(a["due"], b["due"])
        for c in trial["checks"]:
            if c["id"] in (a["request_id"], b["request_id"]):
                c["due"] = due
        rs = rows_of(trial, solve(trial))
        ids = {r["request_id"]: r for r in rs}
        if a["request_id"] not in ids or b["request_id"] not in ids or ids[a["request_id"]]["overtime_shifts"] < 2:
            continue
        u = sum(r["overtime_shifts"] for r in rs)
        cum = 0
        for r in priority(rs):
            if r["request_id"] == a["request_id"]:
                break
            cum += r["overtime_shifts"]
        if 0.3 * u <= cum <= 0.8 * u:
            inst["checks"] = trial["checks"]
            return cum + g.randint(1, ids[a["request_id"]]["overtime_shifts"] - 1), [a["request_id"], b["request_id"]]
    return None


def grants_for(inst, mode, seed, stype):
    """Fleet allowance A from the reference plan's overtime U, split into four base grants (own RNG stream)."""
    g = random.Random(seed * 31337 + 5)
    pair = None
    if stype == "bind":
        got = plant_pair(inst, rows_of(inst, solve(inst)), g)
        if got:
            A, pair = got
    rows = rows_of(inst, solve(inst))
    U = sum(r["overtime_shifts"] for r in rows)
    ub = {b: sum(r["overtime_shifts"] for r in rows if r["base"] == b) for b in inst["bases"]}
    if stype == "slack":
        A = U + g.randint(6, 12)
    elif stype == "cap":
        A = U
    elif stype == "short":
        A = U - 1
    elif pair is None:
        A = int(U * g.uniform(0.4, 0.7))
    if mode == "shipped":
        extra = A - U
        gr = dict(ub)
        for _ in range(extra):
            gr[g.choice(inst["bases"])] += 1
    else:
        while True:
            w = {b: g.uniform(0.5, 1.5) for b in inst["bases"]}
            tw = sum(w.values())
            gr = {b: int(A * w[b] / tw) for b in inst["bases"]}
            gr[inst["bases"][0]] += A - sum(gr.values())
            if any(ub[b] > gr[b] for b in inst["bases"]) and all(v > 0 for v in gr.values()):
                break
    return {"grants": gr, "A": A, "U": U, "U_b": ub, "stype": stype, "pair": pair}


def one(mode, seed, n, empty, out, traps=(), stype="bind"):
    inst = make(mode, seed, n, empty)
    inst["meta"]["traps"] = list(traps)
    inst["meta"].update(grants_for(inst, mode, seed, "slack" if mode == "shipped" else stype))
    render(inst, os.path.join(out, "data"), seed, traps)
    with open(os.path.join(out, "abstract.json"), "w") as f:
        json.dump(inst, f)


if __name__ == "__main__":
    root, ship = sys.argv[1], int(sys.argv[2])
    one("shipped", ship, 5, False, os.path.join(root, "shipped"))
    for k, tok in enumerate(sys.argv[3].split(), start=1):
        s, e, *t = tok.split(":")
        tr = [x for x in t[0].split("+") if x] if t else []
        one("hidden", int(s), 8, e == "1", os.path.join(root, "h%d" % k), tr, t[1] if len(t) > 1 else "bind")
    print("ALL_DONE")
