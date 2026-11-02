"""BRANCH_FIRE and kill check on a rendered data dir.

usage: python3 fire.py <cap_s> <data_dir>...
Per lane: lane.py reference (independent day sweep + fixing pass) vs solve_proto.solve_lane, then every
kill solver labelled against the reference. Per region: which solvers are exact on the whole region.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solve_proto as SP  # noqa: E402
from lane import Lane, reference  # noqa: E402
import lanekill as K  # noqa: E402

SOLVERS = ["g_weight", "g_edf", "g_id", "repair", "g_swap", "bb_id", "bb_heur", "bb_nolex", "nomove", "dp_nofix"]


def lanes_of(data):
    S = SP.build_season(SP.read_inputs(data))
    out = {}
    for R in SP.REGIONS:
        for T in SP.TYPES:
            rs = [r for r in S["reqs"] if r["region"] == R and r["type"] == T]
            pos = {r["id"]: k for k, r in enumerate(rs)}
            inc = [(min(pos[a], pos[b]), max(pos[a], pos[b])) for a, b in S["inc"] if a in pos and b in pos]
            prec = [(pos[a], pos[b]) for a, b in S["prec"] if a in pos and b in pos]
            d = dict(H=SP.H, cap=S["cap"][(R, T)], factor=S["fac"][R], blackout=sorted(S["black"][R]), defer=S["defer"],
                     reqs=[dict(id=r["id"], crews=r["crews"], dur=r["dur"], e=r["e"], l=r["l"], w=r["w"], pub=r["pub"])
                           for r in rs], incompat=inc, prec=prec)
            out[(R, T)] = (d, rs, S)
    return out


def run(cap, data):
    fire = {"S-1": 0, "S-2": 0, "S-3": 0}
    region_ok = {}
    agree = 0
    for (R, T), (d, rs, S) in lanes_of(data).items():
        L = Lane(d)
        t0 = time.time()
        ref = reference(L)
        tref = time.time() - t0
        mine = SP.solve_lane(rs, [(rs[i]["id"], rs[j]["id"]) for i, j in d["incompat"]],
                             [(rs[i]["id"], rs[j]["id"]) for i, j in d["prec"]], d["cap"], d["factor"],
                             set(d["blackout"]), S["defer"])
        same = L.objective(list(mine)) == L.objective(ref) and list(mine) == list(ref)
        agree += same
        heur = sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i))
        plans = {
            "g_weight": K.g_weight(L), "g_edf": K.g_edf(L), "g_id": K.g_id(L), "repair": K.repair(L),
            "g_swap": K.g_swap(L, time.time() + cap),
            "bb_id": K.bb(L, list(range(L.n)), time.time() + cap, seed_plan=K.g_weight(L))[0],
            "bb_heur": K.bb(L, heur, time.time() + cap, seed_plan=K.g_weight(L))[0],
            "bb_nolex": K.bb(L, heur, time.time() + cap, lex=False, seed_plan=K.g_weight(L))[0],
            "nomove": K.nomove(L, d), "dp_nofix": K.dp_tuple_nofix(L),
        }
        labels = {k: K.label(L, p, ref) for k, p in plans.items()}
        if any(labels[k] in ("WRONG:risk", "INFEAS") for k in ("g_weight", "g_edf", "g_id", "repair", "g_swap")):
            fire["S-1"] += 1
        if labels["nomove"] == "WRONG:moved":
            fire["S-2"] += 1
        if labels["dp_nofix"] == "WRONG:tie" or labels["bb_nolex"] == "WRONG:tie":
            fire["S-3"] += 1
        for k, v in labels.items():
            region_ok.setdefault(R, {}).setdefault(k, True)
            if v != "EXACT":
                region_ok[R][k] = False
        print("%s/%s n=%d ref=%.2fs solve_proto=%s %s" % (R, T, L.n, tref, "SAME" if same else "DIFF",
              " ".join("%s=%s" % kv for kv in labels.items())), flush=True)
    print("FIRE", data, fire, "solve_proto agrees on %d/12 lanes" % agree)
    for k in SOLVERS:
        print("REGIONS_EXACT %s %s %d/4" % (os.path.basename(data.rstrip("/")), k,
              sum(region_ok[R][k] for R in region_ok)))


if __name__ == "__main__":
    for dd in sys.argv[2:]:
        run(float(sys.argv[1]), dd)
