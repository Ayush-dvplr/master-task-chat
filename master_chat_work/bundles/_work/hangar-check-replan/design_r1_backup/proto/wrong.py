"""Prototype wrong / alternative solvers for the kill table. Same abstract instance as ref.py.
Each returns {"T": [...], "used": u, "plan": {id: [start, finish, x]}} (deferred = start S+1)."""
import json
import sys

import ref


def cost_of(inst, plan):
    S = inst["S"]
    T1 = T2 = T3 = used = 0
    for ch in inst["checks"]:
        s, f, x = plan[ch["id"]]
        c = inst["classes"][ch["cls"]]
        h = inst["types"][ch["type"]]["h"]
        if s > S:
            T1 += c["pen"]
            T3 += 1
            continue
        T1 += max(0, f - ch["due"]) * c["w"]
        T2 += c["rev"] * (f - s + 1) + inst["shift_cost"] * h * x
        T3 += 1 if s != ch["ps"] else 0
        used += h * x
    return [T1, T2, T3], used


def _per_base(inst, **kw):
    checks = sorted(inst["checks"], key=lambda c: c["id"])
    per = {}
    for b in inst["bases"]:
        cb = [c for c in checks if c["base"] == b]
        per[b] = (cb, ref.solve_base(inst, b, cb, **kw))
    return per


def _assemble(inst, per, alloc):
    plan = {}
    for b, (cb, fr) in per.items():
        v = fr[alloc[b]]
        for k, ch in enumerate(cb):
            plan[ch["id"]] = (v[3][k], v[4][k], v[5][k])
    T, used = cost_of(inst, plan)
    return {"T": T, "used": used, "alloc": alloc, "plan": plan}


def best_within(fr, cap):
    ok = [o for o in fr if o <= cap]
    return min(ok, key=lambda o: fr[o][:5])


def split_fcfs(inst, **kw):
    per = _per_base(inst, **kw)
    left = inst["K"]
    alloc = {}
    for b in inst["bases"]:
        o = best_within(per[b][1], left)
        alloc[b] = o
        left -= o
    return _assemble(inst, per, alloc)


def split_prorata(inst, **kw):
    per = _per_base(inst, **kw)
    want = {b: best_within(per[b][1], 10 ** 9) for b in inst["bases"]}
    tot = sum(want.values())
    K = inst["K"]
    alloc = {}
    for b in inst["bases"]:
        cap = want[b] if tot <= K else (K * want[b]) // tot
        alloc[b] = best_within(per[b][1], cap)
    return _assemble(inst, per, alloc)


def split_marginal(inst, **kw):
    """Start every base at its zero-overtime plan; repeatedly move the base whose next frontier point
    gives the best (T1, T2) gain per shift, while the pool allows."""
    per = _per_base(inst, **kw)
    alloc = {b: 0 for b in inst["bases"]}
    left = inst["K"]
    while True:
        best = None
        for b in inst["bases"]:
            fr = per[b][1]
            cur = fr[alloc[b]]
            nxt = sorted(o for o in fr if o > alloc[b])
            if not nxt:
                continue
            o = nxt[0]
            if o - alloc[b] > left:
                continue
            g1 = (cur[0] - fr[o][0]) / (o - alloc[b])
            g2 = (cur[1] - fr[o][1]) / (o - alloc[b])
            key = (g1, g2)
            if best is None or key > best[0]:
                best = (key, b, o)
        if best is None:
            break
        _, b, o = best
        left -= o - alloc[b]
        alloc[b] = o
    return _assemble(inst, per, alloc)


def exact_variant(inst, **kw):
    """Exact merge over overtime with a per-base variant (allow_ps / defer / tie)."""
    per = _per_base(inst, **kw)
    tie = kw.get("tie", "lex")
    K = inst["K"]
    S = inst["S"]
    ids = sorted(c["id"] for c in inst["checks"])
    pos = {i: k for k, i in enumerate(ids)}
    N = len(ids)

    def key(st):
        t, v = st[0], st[2]
        if tie == "lex":
            return t + (v,)
        if tie == "rev":
            return t + (tuple(-a for a in v),)
        return t

    states = {0: ((0, 0, 0), {}, tuple([S + 1] * 2 * N))}
    for b in inst["bases"]:
        cb, fr = per[b]
        new = {}
        for u, (t, al, vec) in states.items():
            for o, v in fr.items():
                if u + o > K:
                    continue
                vv = list(vec)
                for k, ch in enumerate(cb):
                    vv[pos[ch["id"]]] = v[3][k]
                    vv[N + pos[ch["id"]]] = v[4][k]
                cand = ((t[0] + v[0], t[1] + v[1], t[2] + v[2]), dict(al, **{b: o}), tuple(vv))
                cur = new.get(u + o)
                if cur is None or key(cand) < key(cur):
                    new[u + o] = cand
        states = new
    best = min(states.values(), key=key)
    return _assemble(inst, per, best[1])


def greedy_edd(inst):
    """Earliest-due-date list schedule per base, ASAP; compress when it removes overdue, first come first served."""
    S = inst["S"]
    left = inst["K"]
    tfree = {b: 1 for b in inst["bases"]}
    plan = {}
    for ch in sorted(inst["checks"], key=lambda c: (c["due"], c["id"])):
        b = ch["base"]
        closed = set(inst["closed"].get(b, []))
        nost = set(inst["nostart"].get(b, []))
        ty = inst["types"][ch["type"]]
        lo = max(tfree[b], ch["r"])
        chosen = None
        for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
            if ty["h"] * x > left:
                break
            s = ref.earliest_start(lo, ch["p"] - x, closed, nost, S)
            if s is None:
                continue
            f = s + ch["p"] - x - 1
            chosen = (s, f, x)
            if f <= ch["due"]:
                break
        if chosen is None:
            plan[ch["id"]] = (S + 1, S + 1, 0)
            continue
        s, f, x = chosen
        left -= ty["h"] * x
        tfree[b] = f + 1
        plan[ch["id"]] = chosen
    T, used = cost_of(inst, plan)
    return {"T": T, "used": used, "plan": plan}


def disrupted_repair(inst):
    """Keep every published slot that is still feasible in order; re-place the rest greedily after it."""
    S = inst["S"]
    left = inst["K"]
    plan = {}
    for b in inst["bases"]:
        closed = set(inst["closed"].get(b, []))
        nost = set(inst["nostart"].get(b, []))
        tfree = 1
        todo = []
        for ch in sorted([c for c in inst["checks"] if c["base"] == b], key=lambda c: c["ps"]):
            ps = ch["ps"]
            if ps >= max(tfree, ch["r"]) and ref.feasible_start(ps, ch["p"], closed, nost, S):
                plan[ch["id"]] = (ps, ps + ch["p"] - 1, 0)
                tfree = ps + ch["p"]
            else:
                todo.append(ch)
        for ch in todo:
            ty = inst["types"][ch["type"]]
            chosen = None
            for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
                if ty["h"] * x > left:
                    break
                s = ref.earliest_start(max(tfree, ch["r"]), ch["p"] - x, closed, nost, S)
                if s is None:
                    continue
                chosen = (s, s + ch["p"] - x - 1, x)
                if chosen[1] <= ch["due"]:
                    break
            if chosen is None:
                plan[ch["id"]] = (S + 1, S + 1, 0)
                continue
            left -= ty["h"] * chosen[2]
            tfree = chosen[1] + 1
            plan[ch["id"]] = chosen
    T, used = cost_of(inst, plan)
    return {"T": T, "used": used, "plan": plan}


def joint_exact(inst):
    """Whole-fleet exact search without splitting: memo over (all masks, every line-free day, pool left)."""
    from functools import lru_cache
    S = inst["S"]
    checks = sorted(inst["checks"], key=lambda c: c["id"])
    N = len(checks)
    bases = inst["bases"]
    bi = {b: k for k, b in enumerate(bases)}
    cl = {b: set(inst["closed"].get(b, [])) for b in bases}
    ns = {b: set(inst["nostart"].get(b, [])) for b in bases}

    @lru_cache(maxsize=None)
    def best(mask, tfree, left):
        if mask == 0:
            return (0, 0, 0, (), ())
        # always place the lowest-index remaining check of the earliest-free line? no: try every check
        res = None
        for j in range(N):
            if not mask >> j & 1:
                continue
            ch = checks[j]
            b = bi[ch["base"]]
            c = inst["classes"][ch["cls"]]
            ty = inst["types"][ch["type"]]
            opts = [(S + 1, S + 1, 0, c["pen"], 0, 1, 0)]
            for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
                if ty["h"] * x > left:
                    break
                dur = ch["p"] - x
                for s in range(max(tfree[b], ch["r"]), S - dur + 2):
                    if ref.feasible_start(s, dur, cl[ch["base"]], ns[ch["base"]], S):
                        f = s + dur - 1
                        opts.append((s, f, x, max(0, f - ch["due"]) * c["w"],
                                     c["rev"] * dur + inst["shift_cost"] * ty["h"] * x, int(s != ch["ps"]), ty["h"] * x))
            for s, f, x, a1, a2, a3, ot in opts:
                tf = tfree if s > S else tfree[:b] + (f + 1,) + tfree[b + 1:]
                sub = best(mask & ~(1 << j), tf, left - ot)
                cand = (sub[0] + a1, sub[1] + a2, sub[2] + a3, sub[3] + ((j, s, f, x),), ())
                if res is None or cand[:3] < res[:3]:
                    res = cand
        return res

    r = best((1 << N) - 1, tuple([1] * len(bases)), inst["K"])
    plan = {checks[j]["id"]: (s, f, x) for j, s, f, x in r[3]}
    T, used = cost_of(inst, plan)
    return {"T": T, "used": used, "plan": plan}


SOLVERS = {
    "greedy_edd": greedy_edd,
    "disrupted_repair": disrupted_repair,
    "split_fcfs": split_fcfs,
    "split_prorata": split_prorata,
    "split_marginal": split_marginal,
    "exact_first_tie": lambda i: exact_variant(i, tie="first"),
    "exact_rev_tie": lambda i: exact_variant(i, tie="rev"),
    "exact_asap_only": lambda i: exact_variant(i, allow_ps=False),
    "exact_defer_noslot": lambda i: exact_variant(i, defer="noslot"),
}
SLOW = {"exact_all_starts": lambda i: exact_variant(i, starts="all"), "joint_exact": joint_exact}


def same(a, b):
    return all(tuple(a["plan"][k]) == tuple(b["plan"][k]) for k in a["plan"])


if __name__ == "__main__":
    inst = json.load(open(sys.argv[1]))
    r0 = ref.solve(inst)
    print("ref", r0["T"], r0["used"])
    for name in sys.argv[2:] or SOLVERS:
        r = dict(SOLVERS, **SLOW)[name](inst)
        print(name, r["T"], r["used"], "EXACT" if same(r, r0) else "WRONG")
