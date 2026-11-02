"""Prototype exact solver on an abstract instance (json). Core rules only."""
import json
import sys
from functools import lru_cache


def feasible_start(s, dur, base_closed, base_nostart, S):
    if s in base_nostart:
        return False
    f = s + dur - 1
    if f > S:
        return False
    for d in range(s, f + 1):
        if d in base_closed:
            return False
    return True


def earliest_start(t, dur, closed, nostart, S):
    s = t
    while s + dur - 1 <= S:
        if feasible_start(s, dur, closed, nostart, S):
            return s
        s += 1
    return None


def solve_base(inst, base, checks, allow_ps=True, defer="any", tie="lex", starts="dom"):
    """Return dict overtime -> (T1, T2, T3, starts, finishes, xs) in id order (pareto pruned)."""
    S = inst["S"]
    closed = set(inst["closed"].get(base, []))
    nostart = set(inst["nostart"].get(base, []))
    cls = inst["classes"]
    typ = inst["types"]
    rate = inst["shift_cost"]
    n = len(checks)
    full = (1 << n) - 1
    if tie == "lex":
        KEY = lambda v: v[:5]
    elif tie == "rev":
        KEY = lambda v: v[:3] + (tuple(-a for a in v[3]), tuple(-a for a in v[4]))
    else:
        KEY = lambda v: v[:3]
    es_cache = {}

    def es(t, dur):
        key = (t, dur)
        if key not in es_cache:
            es_cache[key] = earliest_start(t, dur, closed, nostart, S)
        return es_cache[key]

    @lru_cache(maxsize=None)
    def best(mask, tfree):
        if mask == 0:
            z = (0,) * n
            return ((0, (0, 0, 0, z, z, z)),)
        out = {}
        for j in range(n):
            if not mask >> j & 1:
                continue
            ch = checks[j]
            rest = mask & ~(1 << j)
            c = cls[ch["cls"]]
            ty = typ[ch["type"]]
            opts = []
            lo = max(tfree, ch["r"])
            ps = ch["ps"]
            for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
                dur = ch["p"] - x
                a = es(lo, dur)
                cand = [a] if a is not None else []
                if starts == "all" and a is not None:
                    cand = [s for s in range(a, S - dur + 2) if feasible_start(s, dur, closed, nostart, S)]
                    opts.extend((s, s + dur - 1, x, max(0, s + dur - 1 - ch["due"]) * c["w"],
                                 c["rev"] * dur + rate * ty["h"] * x, 1 if s != ps else 0, ty["h"] * x) for s in cand)
                    continue
                if allow_ps and ps >= lo and ps != a and feasible_start(ps, dur, closed, nostart, S):
                    cand.append(ps)
                for s in cand:
                    f = s + dur - 1
                    opts.append((s, f, x, max(0, f - ch["due"]) * c["w"],
                                 c["rev"] * dur + rate * ty["h"] * x, 1 if s != ps else 0, ty["h"] * x))
            if defer == "any" or not opts:
                opts.insert(0, (S + 1, S + 1, 0, c["pen"], 0, 1, 0))
            for s, f, x, a1, a2, a3, ot in opts:
                sub = best(rest, tfree if s > S else f + 1)
                for o, v in sub:
                    st = v[3][:j] + (s,) + v[3][j + 1:]
                    fi = v[4][:j] + (f,) + v[4][j + 1:]
                    xs = v[5][:j] + (x,) + v[5][j + 1:]
                    cand = (v[0] + a1, v[1] + a2, v[2] + a3, st, fi, xs)
                    oo = o + ot
                    cur = out.get(oo)
                    if cur is None or KEY(cand) < KEY(cur):
                        out[oo] = cand
        res = []
        bestv = None
        for o in sorted(out):
            v = out[o]
            if bestv is None or KEY(v) < bestv:
                res.append((o, v))
                bestv = KEY(v)
        return tuple(res)

    return dict(best(full, 1))


def solve(inst):
    bases = inst["bases"]
    checks = sorted(inst["checks"], key=lambda c: c["id"])
    order = {c["id"]: i for i, c in enumerate(checks)}
    per = {}
    for b in bases:
        cb = [c for c in checks if c["base"] == b]
        per[b] = (cb, solve_base(inst, b, cb))
    K = inst["K"]
    N = len(checks)
    S = inst["S"]
    # merge: state used -> (T1,T2,T3, fleet start list, fleet finish list, choice dict)
    states = {0: (0, 0, 0, [S + 1] * N, [S + 1] * N, {})}
    for b in bases:
        cb, fr = per[b]
        new = {}
        for u, sv in states.items():
            for o, v in fr.items():
                if u + o > K:
                    continue
                st = list(sv[3])
                fi = list(sv[4])
                for k, ch in enumerate(cb):
                    st[order[ch["id"]]] = v[3][k]
                    fi[order[ch["id"]]] = v[4][k]
                cand = (sv[0] + v[0], sv[1] + v[1], sv[2] + v[2], st, fi, dict(sv[5], **{b: o}))
                cur = new.get(u + o)
                if cur is None or cand[:3] + (cand[3], cand[4]) < cur[:3] + (cur[3], cur[4]):
                    new[u + o] = cand
        states = new
    bestv = min(states.values(), key=lambda v: (v[0], v[1], v[2], v[3], v[4]))
    plan = {}
    for b in bases:
        cb, fr = per[b]
        v = fr[bestv[5][b]]
        for k, ch in enumerate(cb):
            plan[ch["id"]] = (v[3][k], v[4][k], v[5][k])
    used = sum(bestv[5].values())
    return {"T": [bestv[0], bestv[1], bestv[2]], "used": used, "alloc": bestv[5], "plan": plan}


if __name__ == "__main__":
    inst = json.load(open(sys.argv[1]))
    r = solve(inst)
    print(json.dumps(r, sort_keys=True))
