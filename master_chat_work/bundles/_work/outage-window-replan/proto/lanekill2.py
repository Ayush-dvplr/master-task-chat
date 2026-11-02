"""Stronger generic solvers for the kill test: window-overlap components + B&B, and long-cap B&B.
usage: python3 lanekill2.py <cap_s> <tier> <seed>..."""
import sys
import time
from lanegen import gen_lane
from lane import Lane, reference
from lanekill import bb, g_weight, label


def components(L):
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
    for i in range(L.n):
        for j in range(i + 1, L.n):
            a, b = span[i], span[j]
            if a and b and a[0] <= b[1] and b[0] <= a[1]:
                par[f(i)] = f(j)
    for i, j in L.incompat + L.prec:
        par[f(i)] = f(j)
    g = {}
    for i in range(L.n):
        g.setdefault(f(i), []).append(i)
    return sorted(g.values())


def sub(d, members):
    idx = {m: k for k, m in enumerate(members)}
    e = dict(d)
    e["reqs"] = [d["reqs"][m] for m in members]
    e["incompat"] = [(idx[i], idx[j]) for i, j in d["incompat"] if i in idx and j in idx]
    e["prec"] = [(idx[i], idx[j]) for i, j in d["prec"] if i in idx and j in idx]
    return e


def comp_bb(d, L, cap, heur):
    plan = [None] * L.n
    capped = False
    t_end = time.time() + cap
    for comp in components(L):
        S = Lane(sub(d, comp))
        order = list(range(S.n))
        if heur:
            order.sort(key=lambda i: (-S.reqs[i]["w"] * S.reqs[i]["dur"], i))
        p, c, _ = bb(S, order, t_end, seed_plan=g_weight(S))
        capped |= c
        for k, m in enumerate(comp):
            plan[m] = p[k]
    return plan, capped


def main():
    cap = float(sys.argv[1])
    tier = sys.argv[2]
    for sd in [int(x) for x in sys.argv[3:]]:
        d = gen_lane(sd, tier)
        L = Lane(d)
        ref = reference(L)
        sizes = [len(c) for c in components(L)]
        row = ["seed=%d n=%d comps=%s" % (sd, L.n, sizes)]
        for nm, heur in [("comp_id", False), ("comp_heur", True)]:
            t0 = time.time()
            p, c = comp_bb(d, L, cap, heur)
            row.append("%s=%s%s(%.2f)" % (nm, label(L, p, ref), "/capped" if c else "", time.time() - t0))
        print(" ".join(row), flush=True)


if __name__ == "__main__":
    main()
