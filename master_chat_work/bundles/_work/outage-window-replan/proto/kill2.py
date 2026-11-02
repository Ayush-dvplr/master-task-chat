"""Option (c) kill table: whole-corpus budget LIMIT seconds per solver (as the stated per-run limit).
usage: python3 kill2.py <limit_s> <data_dir>...
Rows: ref (lane.py DP), solve_proto (lex-carrying DP), comp_dfs (contention components + id-order exact DFS,
no guard: TIMEOUT if over limit), comp_dfs_guard (same, returns incumbents at 0.8*limit), bb_heur_guard,
greedy family, nomove, dp_nofix. Prints per solver: seconds, regions exact k/4, verdict."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fire import lanes_of  # noqa: E402
from lane import Lane, reference  # noqa: E402
import lanekill as K  # noqa: E402
from lanekill2 import sub  # noqa: E402
import solve_proto as SP  # noqa: E402


def contention_components(L):
    """Blind-style split: two requests join when some day both windows cover is over-subscribed."""
    par = list(range(L.n))

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    span = []
    for i in range(L.n):
        st = [s for s in L.opts[i] if s != L.DEF]
        span.append((min(st), max(st) + L.reqs[i]["dur"] - 1) if st else None)
    for d in range(1, L.H + 1):
        cov = [i for i in range(L.n) if span[i] and span[i][0] <= d <= span[i][1]]
        if sum(L.reqs[i]["crews"] for i in cov) > L.cap[d]:
            for i in cov[1:]:
                par[f(i)] = f(cov[0])
    for i, j in L.incompat:
        a, b = span[i], span[j]
        if a and b and a[0] <= b[1] and b[0] <= a[1]:
            par[f(i)] = f(j)
    for i, j in L.prec:
        par[f(i)] = f(j)
    g = {}
    for i in range(L.n):
        g.setdefault(f(i), []).append(i)
    return sorted(g.values())


def comp_dfs(d, L, deadline, heur=False):
    plan = [None] * L.n
    capped = False
    for comp in contention_components(L):
        S = Lane(sub(d, comp))
        order = list(range(S.n))
        if heur:
            order.sort(key=lambda i: (-S.reqs[i]["w"] * S.reqs[i]["dur"], i))
        p, c, _ = K.bb(S, order, deadline, seed_plan=K.g_weight(S))
        capped |= c
        for k, m in enumerate(comp):
            plan[m] = p[k] if p else None
    return plan, capped


def run(limit, data):
    lanes = lanes_of(data)
    refs = {}
    t0 = time.time()
    for key, (d, rs, S) in lanes.items():
        refs[key] = reference(Lane(d))
    t_ref = time.time() - t0
    t0 = time.time()
    for key, (d, rs, S) in lanes.items():
        SP.solve_lane(rs, [(rs[i]["id"], rs[j]["id"]) for i, j in d["incompat"]],
                      [(rs[i]["id"], rs[j]["id"]) for i, j in d["prec"]], d["cap"], d["factor"],
                      set(d["blackout"]), S["defer"])
    t_sp = time.time() - t0
    name = os.path.basename(data.rstrip("/"))
    print("ROW %s ref_lane_dp %.2fs EXACT 4/4" % (name, t_ref))
    print("ROW %s solve_proto_lexdp %.2fs EXACT 4/4" % (name, t_sp))
    maxn = max(Lane(d).n for d, _, _ in lanes.values())
    maxc = max(max(len(c) for c in contention_components(Lane(d))) for d, _, _ in lanes.values())
    print("SIZE %s max_lane_n %d max_contention_comp %d" % (name, maxn, maxc))

    solvers = ["comp_dfs", "comp_dfs_guard", "comp_heur_guard", "bb_heur_guard", "g_weight", "g_swap", "repair",
               "nomove", "dp_nofix"]
    if os.environ.get("KILL_SOLVERS"):
        solvers = os.environ["KILL_SOLVERS"].split(",")
    for sv in solvers:
        start = time.time()
        deadline = start + (limit if sv == "comp_dfs" else 0.8 * limit)
        ok = {}
        timed_out = False
        for (R, T), (d, rs, S) in lanes.items():
            L = Lane(d)
            if sv == "comp_dfs":
                p, c = comp_dfs(d, L, deadline)
                if c:
                    timed_out = True
                    break
            elif sv == "comp_dfs_guard":
                p, _ = comp_dfs(d, L, deadline)
            elif sv == "comp_heur_guard":
                p, _ = comp_dfs(d, L, deadline, heur=True)
            elif sv == "bb_heur_guard":
                heur = sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i))
                p = K.bb(L, heur, deadline, seed_plan=K.g_weight(L))[0]
            elif sv == "g_weight":
                p = K.g_weight(L)
            elif sv == "g_swap":
                p = K.g_swap(L, min(deadline, time.time() + 2))
            elif sv == "repair":
                p = K.repair(L)
            elif sv == "nomove":
                p = K.nomove(L, d)
            else:
                p = K.dp_tuple_nofix(L)
            lab = K.label(L, p, refs[(R, T)]) if p is not None and None not in p else "NONE"
            ok[R] = ok.get(R, True) and lab == "EXACT"
        secs = time.time() - start
        if timed_out:
            print("ROW %s %s %.1fs TIMEOUT 0/4" % (name, sv, secs), flush=True)
        else:
            k = sum(ok.values())
            print("ROW %s %s %.1fs %s %d/4" % (name, sv, secs, "EXACT" if k == 4 else "WRONG", k), flush=True)


if __name__ == "__main__":
    for dd in sys.argv[2:]:
        run(float(sys.argv[1]), dd)
