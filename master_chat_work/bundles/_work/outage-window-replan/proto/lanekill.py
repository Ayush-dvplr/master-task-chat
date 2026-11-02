"""Kill test on lanes. usage: python3 lanekill.py <cap_s> <tier> <seed>... [--brute]"""
import sys
import time
import itertools

from lane import Lane, reference, SCALE
from lanegen import gen_lane


class TO(Exception):
    pass


def brute(L):
    best = None
    for plan in itertools.product(*L.opts):
        plan = list(plan)
        if L.feasible(plan):
            o = L.objective(plan)
            if best is None or o < best:
                best = o
    return list(best[2])


def place_ok(L, plan, i, s, use):
    if s == L.DEF:
        for p in L.pred_of[i]:
            pass
        for q in L.succ_of[i]:
            if plan[q] is not None and plan[q] != L.DEF:
                return False
        return True
    r = L.reqs[i]
    for x in range(s, s + r["dur"]):
        if use[x] + r["crews"] > L.cap[x]:
            return False
    for j in L.inc_of[i]:
        b = plan[j]
        if b is not None and b != L.DEF and s < b + L.reqs[j]["dur"] and b < s + r["dur"]:
            return False
    for p in L.pred_of[i]:
        a = plan[p]
        if a == L.DEF:
            return False
        if a is not None and s < a + L.reqs[p]["dur"]:
            return False
    for q in L.succ_of[i]:
        b = plan[q]
        if b is not None and b != L.DEF and b < s + r["dur"]:
            return False
    return True


def apply(L, use, i, s, sign):
    if s == L.DEF:
        return
    r = L.reqs[i]
    for x in range(s, s + r["dur"]):
        use[x] += sign * r["crews"]


def greedy(L, order):
    plan = [None] * L.n
    use = [0] * (L.H + 2)
    for i in order:
        best = None
        for s in L.opts[i]:
            if place_ok(L, plan, i, s, use):
                k = (L.val(i, s), s)
                if best is None or k < best:
                    best = k
        s = best[1] if best else L.DEF
        plan[i] = s
        apply(L, use, i, s, 1)
    for i in range(L.n):
        for p in L.pred_of[i]:
            if plan[p] == L.DEF and plan[i] != L.DEF:
                apply(L, use, i, plan[i], -1)
                plan[i] = L.DEF
    return plan


def g_weight(L):
    return greedy(L, sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i)))


def g_edf(L):
    return greedy(L, sorted(range(L.n), key=lambda i: (L.reqs[i]["l"], i)))


def g_id(L):
    return greedy(L, list(range(L.n)))


def local_search(L, plan, deadline):
    plan = list(plan)
    cur = L.objective(plan)
    improved = True
    while improved:
        improved = False
        if time.time() > deadline:
            break
        for i in range(L.n):
            for s in L.opts[i]:
                if s == plan[i]:
                    continue
                p2 = list(plan)
                p2[i] = s
                if L.feasible(p2):
                    o = L.objective(p2)
                    if o < cur:
                        plan, cur, improved = p2, o, True
        if improved:
            continue
        for i in range(L.n):
            for j in range(i + 1, L.n):
                if time.time() > deadline:
                    return plan
                for s in L.opts[i]:
                    for t in L.opts[j]:
                        if s == plan[i] and t == plan[j]:
                            continue
                        p2 = list(plan)
                        p2[i] = s
                        p2[j] = t
                        if L.feasible(p2):
                            o = L.objective(p2)
                            if o < cur:
                                plan, cur, improved = p2, o, True
                if improved:
                    break
            if improved:
                break
    return plan


def g_swap(L, deadline):
    return local_search(L, g_weight(L), deadline)


def repair(L):
    plan = [None] * L.n
    use = [0] * (L.H + 2)
    for i in range(L.n):
        p = L.reqs[i]["pub"]
        if p is not None and p in L.cost[i] and place_ok(L, plan, i, p, use):
            plan[i] = p
            apply(L, use, i, p, 1)
    rest = [i for i in range(L.n) if plan[i] is None]
    rest.sort(key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i))
    for i in rest:
        best = None
        for s in L.opts[i]:
            if place_ok(L, plan, i, s, use):
                k = (L.val(i, s), s)
                if best is None or k < best:
                    best = k
        s = best[1] if best else L.DEF
        plan[i] = s
        apply(L, use, i, s, 1)
    return plan


def bb(L, order, deadline, lex=True, seed_plan=None):
    """Opus-like exact DFS: order of requests, options by value, LB = sum of min values of the rest.
    lex=True compares full (cost, moved, vector); stops at deadline and returns incumbent."""
    minv = [min(L.val(i, s) for s in L.opts[i]) for i in range(L.n)]
    suffix = [0] * (L.n + 1)
    for k in range(L.n - 1, -1, -1):
        suffix[k] = suffix[k + 1] + minv[order[k]]
    best = [None, None]
    if seed_plan is not None and L.feasible(seed_plan):
        best = [L.objective(seed_plan), list(seed_plan)]
    plan = [None] * L.n
    use = [0] * (L.H + 2)
    nodes = [0]
    capped = [False]

    def rec(k, v):
        nodes[0] += 1
        if nodes[0] % 2000 == 0 and time.time() > deadline:
            capped[0] = True
            raise TO()
        if best[0] is not None:
            bv = best[0][0] * SCALE + best[0][1]
            if v + suffix[k] > bv or (not lex and v + suffix[k] >= bv):
                return
        if k == L.n:
            o = L.objective(plan)
            if best[0] is None or (o < best[0] if lex else (o[0], o[1]) < (best[0][0], best[0][1])):
                best[0], best[1] = o, list(plan)
            return
        i = order[k]
        for s in sorted(L.opts[i], key=lambda s: (L.val(i, s), s)):
            if place_ok(L, plan, i, s, use):
                plan[i] = s
                apply(L, use, i, s, 1)
                rec(k + 1, v + L.val(i, s))
                apply(L, use, i, s, -1)
                plan[i] = None

    try:
        rec(0, 0)
    except TO:
        pass
    return best[1], capped[0], nodes[0]


def dp_tuple_nofix(L):
    """DP that keeps min (value) per state and backtracks first optimum (ties unresolved)."""
    from lane import dp_nofix
    return dp_nofix(L)


def nomove(L, d):
    import copy
    d2 = copy.deepcopy(d)
    for r in d2["reqs"]:
        r["pub"] = None
    return reference(Lane(d2))


def label(L, plan, ref):
    if plan is None:
        return "NONE"
    if not L.feasible(plan):
        return "INFEAS"
    a, b = L.objective(plan), L.objective(ref)
    if a == b:
        return "EXACT"
    if a[0] != b[0]:
        return "WRONG:risk"
    if a[1] != b[1]:
        return "WRONG:moved"
    return "WRONG:tie"


def main():
    cap = float(sys.argv[1])
    tier = sys.argv[2]
    seeds = [int(x) for x in sys.argv[3:] if not x.startswith("--")]
    do_brute = "--brute" in sys.argv
    for sd in seeds:
        d = gen_lane(sd, tier)
        L = Lane(d)
        t0 = time.time()
        ref = reference(L)
        tref = time.time() - t0
        row = ["seed=%d n=%d ref=%.2fs" % (sd, L.n, tref)]
        if do_brute:
            br = brute(L)
            row.append("brute=" + ("OK" if L.objective(br) == L.objective(ref) else "MISMATCH %s %s" % (L.objective(br)[:2], L.objective(ref)[:2])))
        for name, fn in [("g_weight", g_weight), ("g_edf", g_edf), ("g_id", g_id), ("repair", repair)]:
            t0 = time.time()
            p = fn(L)
            row.append("%s=%s(%.2f)" % (name, label(L, p, ref), time.time() - t0))
        t0 = time.time()
        p = g_swap(L, time.time() + cap)
        row.append("g_swap=%s(%.2f)" % (label(L, p, ref), time.time() - t0))
        for nm, order in [("bb_id", list(range(L.n))), ("bb_heur", sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i)))]:
            t0 = time.time()
            p, capped, nodes = bb(L, order, time.time() + cap, seed_plan=g_weight(L))
            row.append("%s=%s%s(%.2f,%dn)" % (nm, label(L, p, ref), "/capped" if capped else "", time.time() - t0, nodes))
        t0 = time.time()
        p, capped, nodes = bb(L, sorted(range(L.n), key=lambda i: (-L.reqs[i]["w"] * L.reqs[i]["dur"], i)), time.time() + cap, lex=False, seed_plan=g_weight(L))
        row.append("bb_nolex=%s%s(%.2f)" % (label(L, p, ref), "/capped" if capped else "", time.time() - t0))
        t0 = time.time()
        p = nomove(L, d)
        row.append("nomove=%s(%.2f)" % (label(L, p, ref), time.time() - t0))
        t0 = time.time()
        p = dp_tuple_nofix(L)
        row.append("dp_nofix=%s(%.2f)" % (label(L, p, ref), time.time() - t0))
        print(" ".join(row), flush=True)


if __name__ == "__main__":
    main()
