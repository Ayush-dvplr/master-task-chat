"""Kill test runner: python3 kill.py <tier> <seed>... ; prints one line per solver per seed."""
import sys
import time
import core
import gen_proto

CAP_S = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
TIER = sys.argv[2]
SEEDS = [int(x) for x in sys.argv[3:]]


def plan_from(I, asg):
    return [asg[i] for i in range(I.n)]


def s_greedy_w(I):
    return core.greedy(I, sorted(range(I.n), key=lambda i: (-I.reqs[i]["w"], i)))


def s_edf(I):
    return core.greedy(I, sorted(range(I.n), key=lambda i: (I.reqs[i]["l"], I.reqs[i]["e"], i)))


def s_greedy_swap(I, deadline):
    plan = s_greedy_w(I)
    if plan is None:
        return None
    best = I.objective(plan)
    improved = True
    while improved and time.time() < deadline:
        improved = False
        for i in range(I.n):
            for s in I.opts[i]:
                if s == plan[i]:
                    continue
                p2 = list(plan)
                p2[i] = s
                if I.feasible(p2):
                    v = I.objective(p2)
                    if v < best:
                        plan, best, improved = p2, v, True
        if improved:
            continue
        for i in range(I.n):
            for j in range(i + 1, I.n):
                ri, rj = I.reqs[i], I.reqs[j]
                if ri["type"] != rj["type"]:
                    continue
                if not (ri["e"] <= rj["l"] and rj["e"] <= ri["l"]):
                    continue
                for s in I.opts[i]:
                    for t in I.opts[j]:
                        if s == plan[i] and t == plan[j]:
                            continue
                        p2 = list(plan)
                        p2[i] = s
                        p2[j] = t
                        if I.feasible(p2):
                            v = I.objective(p2)
                            if v < best:
                                plan, best, improved = p2, v, True
                if time.time() > deadline:
                    return plan
    return plan


def s_repair(I):
    st = core.State(I)
    order = []
    for i in range(I.n):
        p = I.reqs[i]["pub"]
        if p is not None and p in I.cost[i] and st.ok(i, p):
            st.put(i, p)
        else:
            order.append(i)
    for i in sorted(order, key=lambda i: (-I.reqs[i]["w"], i)):
        s = core.greedy_pick(I, st, i)
        if s == I.DEF:
            core.force_defer(I, st, i)
        st.put(i, s)
    plan = [st.asg[i] for i in range(I.n)]
    return plan if I.feasible(plan) else None


def s_capped_region(I, deadline):
    g = s_greedy_w(I)
    init = None
    if g is not None:
        v = I.objective(g)
        init = ((v[0], v[1]), {i: g[i] for i in range(I.n)})
    idx = list(range(I.n))
    v, a, to = core.bb(I, idx, core.order_heur(I, idx), init=init, deadline=deadline)
    return plan_from(I, a), to


def s_comp_heur(I, deadline):
    plan = [None] * I.n
    to = False
    for comp in core.components(I):
        v, a, t = core.bb(I, comp, core.order_heur(I, comp), deadline=deadline)
        to = to or t
        if a is None:
            return None, True
        for i in comp:
            plan[i] = a[i]
    return plan, to


def s_comp_id(I, deadline):
    plan = [None] * I.n
    to = False
    for comp in core.components(I):
        v, a, t = core.bb(I, comp, sorted(comp), deadline=deadline)
        to = to or t
        if a is None:
            return None, True
        for i in comp:
            plan[i] = a[i]
    return plan, to


def s_region_id(I, deadline):
    idx = list(range(I.n))
    v, a, to = core.bb(I, idx, idx, deadline=deadline)
    if a is None:
        return None, True
    return plan_from(I, a), to


def main():
    for seed in SEEDS:
        t0 = time.time()
        regions = gen_proto.gen(seed, TIER)
        tg = time.time() - t0
        insts = [core.Inst(r) for r in regions]
        res = {}
        t0 = time.time()
        refs = [core.reference(I) for I in insts]
        res["REF"] = (time.time() - t0, "EXACT")
        ncomp = [max(len(c) for c in core.components(I)) for I in insts]
        nreq = [I.n for I in insts]
        solvers = [
            ("greedy_w", lambda I, dl: (s_greedy_w(I), False)),
            ("edf", lambda I, dl: (s_edf(I), False)),
            ("greedy_swap", lambda I, dl: (s_greedy_swap(I, dl), time.time() > dl)),
            ("repair", lambda I, dl: (s_repair(I), False)),
            ("capped_region", s_capped_region),
            ("comp_heur", s_comp_heur),
            ("comp_id", s_comp_id),
            ("region_id", s_region_id),
        ]
        for name, fn in solvers:
            t0 = time.time()
            wrong_regions = []
            tos = 0
            for k, I in enumerate(insts):
                dl = time.time() + CAP_S
                plan, to = fn(I, dl)
                tos += 1 if to else 0
                if plan is None or plan != refs[k]:
                    if plan is None or not I.feasible(plan):
                        wrong_regions.append(regions[k]["name"] + ":INFEAS")
                    else:
                        vo, vr = I.objective(plan), I.objective(refs[k])
                        lvl = "risk" if vo[0] != vr[0] else ("moved" if vo[1] != vr[1] else "tie")
                        assert vo > vr, (name, vo[:2], vr[:2])
                        wrong_regions.append(regions[k]["name"] + ":" + lvl)
            dt = time.time() - t0
            verdict = "EXACT" if not wrong_regions else "WRONG"
            if tos:
                verdict += "(capped %d)" % tos
            res[name] = (dt, verdict + " " + ",".join(wrong_regions))
        print("seed %d tier %s gen %.1fs nreq %s maxcomp %s" % (seed, TIER, tg, nreq, ncomp), flush=True)
        for k, (dt, v) in res.items():
            print("  %-14s %7.2fs %s" % (k, dt, v), flush=True)


main()
