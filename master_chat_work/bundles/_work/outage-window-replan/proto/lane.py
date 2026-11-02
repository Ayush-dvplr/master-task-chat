"""Lane model (one region x one crew type) and exact day-sweep reference (prototype, kill test only).

Lane dict:
  H, cap[d] (crews available on day d, index 0..H+1), factor[d], blackout (set of days, no starts),
  reqs: list sorted by asset id of dict id, crews, dur, e, l, w, pub (start day, DEF, or None for new)
  incompat: list of (i, j) index pairs, never out on a common day
  prec: list of (i, j): j starts no earlier than the day after i ends; i deferred => j deferred
Objective (lexicographic): total cost, moved count, start vector in asset-id order (DEF = H + 1 ranks last).
Cost of a start s: w * sum factor[s .. s+dur-1]; cost of deferral: w * dur * DEFER_FACTOR.
"""
import time

DEFER_FACTOR = 4
SCALE = 100000  # value = cost * SCALE + moved


class Lane:
    def __init__(self, d):
        self.H = d["H"]
        self.DEF = self.H + 1
        self.cap = d["cap"]
        self.factor = d["factor"]
        self.blackout = set(d["blackout"])
        self.reqs = d["reqs"]
        self.defer = d.get("defer", DEFER_FACTOR)
        self.n = len(self.reqs)
        self.incompat = [tuple(x) for x in d["incompat"]]
        self.prec = [tuple(x) for x in d["prec"]]
        n = self.n
        self.inc_of = [set() for _ in range(n)]
        for i, j in self.incompat:
            self.inc_of[i].add(j)
            self.inc_of[j].add(i)
        self.pred_of = [[] for _ in range(n)]
        self.succ_of = [[] for _ in range(n)]
        for i, j in self.prec:
            self.pred_of[j].append(i)
            self.succ_of[i].append(j)
        self.is_pred = frozenset(i for i, _ in self.prec)
        self.ls = [r["l"] - r["dur"] + 1 for r in self.reqs]
        self.opts = []
        self.cost = []
        for k, r in enumerate(self.reqs):
            o = []
            c = {}
            for s in range(r["e"], self.ls[k] + 1):
                if s in self.blackout:
                    continue
                if all(self.cap[x] >= r["crews"] for x in range(s, s + r["dur"])):
                    o.append(s)
                    c[s] = r["w"] * sum(self.factor[x] for x in range(s, s + r["dur"]))
            o.append(self.DEF)
            c[self.DEF] = r["w"] * r["dur"] * self.defer
            self.opts.append(o)
            self.cost.append(c)

    def moved(self, i, s):
        p = self.reqs[i]["pub"]
        return 0 if p is None or p == s else 1

    def val(self, i, s):
        return self.cost[i][s] * SCALE + self.moved(i, s)

    def objective(self, plan):
        v = sum(self.val(i, plan[i]) for i in range(self.n))
        return (v // SCALE, v % SCALE, tuple(plan))

    def feasible(self, plan):
        use = [0] * (self.H + 2)
        for i, s in enumerate(plan):
            if s == self.DEF:
                continue
            if s not in self.cost[i]:
                return False
            r = self.reqs[i]
            for x in range(s, s + r["dur"]):
                use[x] += r["crews"]
                if use[x] > self.cap[x]:
                    return False
        for i, j in self.incompat:
            a, b = plan[i], plan[j]
            if a != self.DEF and b != self.DEF and a < b + self.reqs[j]["dur"] and b < a + self.reqs[i]["dur"]:
                return False
        for i, j in self.prec:
            a, b = plan[i], plan[j]
            if a == self.DEF and b != self.DEF:
                return False
            if a != self.DEF and b != self.DEF and b < a + self.reqs[i]["dur"]:
                return False
        return True


def sweep(L, fixed, store_edges=True, deadline=None, order_big_first=False):
    """Forward day sweep. fixed: dict i -> start or DEF. Returns (opt value, edges per day, fwd per day)."""
    H = L.H
    reqs = L.reqs
    arrive = [[] for _ in range(H + 2)]
    for i, r in enumerate(reqs):
        arrive[r["e"]].append(i)
    expire = [[] for _ in range(H + 2)]
    for i in range(L.n):
        ls = min(L.ls[i], H)
        if ls < reqs[i]["e"]:
            ls = reqs[i]["e"]
        expire[ls].append(i)
    start_state = (frozenset(), (), frozenset())
    fwd = {start_state: 0}
    days = []
    for d in range(1, H + 1):
        if deadline is not None and time.time() > deadline:
            raise TimeoutError()
        nxt = {}
        edges = [] if store_edges else None
        for st, fv in fwd.items():
            pend, run, dset = st
            if arrive[d]:
                pend = pend | frozenset(arrive[d])
            run_now = [(e, i) for (e, i) in run if e >= d]
            # eligible to start today
            elig = []
            if d not in L.blackout:
                for i in sorted(pend):
                    f = fixed.get(i)
                    if f is not None and f != d:
                        continue
                    if d not in L.cost[i]:
                        continue
                    okp = True
                    for p in L.pred_of[i]:
                        if p in pend or p in dset or reqs[p]["e"] >= d or any(q == p for _, q in run_now):
                            okp = False
                            break
                    if not okp:
                        continue
                    if any(q in L.inc_of[i] for _, q in run_now):
                        continue
                    elig.append(i)
            occ = {}
            for e, i in run_now:
                c = reqs[i]["crews"]
                for x in range(d, e + 1):
                    occ[x] = occ.get(x, 0) + c
            subsets = []

            def rec(k, chosen, occ_local):
                if k == len(elig):
                    subsets.append(tuple(chosen))
                    return
                rec(k + 1, chosen, occ_local)
                i = elig[k]
                r = reqs[i]
                if any(q in L.inc_of[i] for q in chosen):
                    return
                for x in range(d, d + r["dur"]):
                    if occ_local.get(x, 0) + r["crews"] > L.cap[x]:
                        return
                o2 = dict(occ_local)
                for x in range(d, d + r["dur"]):
                    o2[x] = o2.get(x, 0) + r["crews"]
                chosen.append(i)
                rec(k + 1, chosen, o2)
                chosen.pop()

            rec(0, [], occ)
            if order_big_first:
                subsets.sort(key=lambda s: -len(s))
            for S in subsets:
                add = 0
                for i in S:
                    add += L.val(i, d)
                p2 = pend.difference(S)
                dfr = []
                for i in expire[d]:
                    if i in p2:
                        f = fixed.get(i)
                        dfr.append(i)
                bad = False
                for i in dfr:
                    f = fixed.get(i)
                    if f is not None and f != L.DEF:
                        bad = True
                        break
                    add += L.val(i, L.DEF)
                if bad:
                    continue
                if dfr:
                    p2 = p2.difference(dfr)
                d2 = dset
                for i in dfr:
                    if i in L.is_pred:
                        d2 = d2 | {i}
                r2 = [(e, i) for (e, i) in run_now if e >= d + 1]
                for i in S:
                    e = d + reqs[i]["dur"] - 1
                    if e >= d + 1:
                        r2.append((e, i))
                k2 = (p2, tuple(sorted(r2)), d2)
                v2 = fv + add
                if store_edges:
                    edges.append((st, k2, add, S, tuple(dfr)))
                if k2 not in nxt or v2 < nxt[k2]:
                    nxt[k2] = v2
        days.append((fwd, edges))
        fwd = nxt
    # all requests must be resolved at end (pending empty, nothing running beyond H handled by cap index)
    final = {k: v for k, v in fwd.items() if not k[0]}
    if not final:
        return None, days, final
    return min(final.values()), days, final


def optimal_options(L, fixed):
    opt, days, final = sweep(L, fixed)
    if opt is None:
        return None, None
    # backward values
    bwd = {k: 0 for k, v in final.items()}
    sets = [set() for _ in range(L.n)]
    per_day_bwd = [None] * len(days)
    for idx in range(len(days) - 1, -1, -1):
        fwd, edges = days[idx]
        b = {}
        for st, k2, add, S, dfr in edges:
            if k2 in bwd:
                v = add + bwd[k2]
                if st not in b or v < b[st]:
                    b[st] = v
        per_day_bwd[idx] = (bwd, b)
        bwd = b
    for idx, (fwd, edges) in enumerate(days):
        bnext, _ = per_day_bwd[idx]
        d = idx + 1
        for st, k2, add, S, dfr in edges:
            if k2 in bnext and fwd[st] + add + bnext[k2] == opt:
                for i in S:
                    sets[i].add(d)
                for i in dfr:
                    sets[i].add(L.DEF)
    return opt, sets


def reference(L, counter=None):
    fixed = {}
    opt0 = None
    i = 0
    opt, sets = optimal_options(L, fixed)
    opt0 = opt
    runs = 1
    while i < L.n:
        s = sets[i]
        if len(s) == 1:
            fixed[i] = next(iter(s))
            i += 1
            continue
        fixed[i] = min(s)
        i += 1
        opt, sets = optimal_options(L, fixed)
        runs += 1
        assert opt == opt0
    if counter is not None:
        counter[0] += runs
    return [fixed[i] for i in range(L.n)]


def dp_nofix(L, big_first=False):
    """Plain sweep with natural backtrack (first optimal edge per day in enumeration order)."""
    opt, days, final = sweep(L, {}, order_big_first=big_first)
    if opt is None:
        return None
    # backtrack from best final state
    best_k = min((v, k) for k, v in final.items() if True)[1] if False else None
    target = None
    for k, v in final.items():
        if v == opt:
            target = k
            break
    plan = [None] * L.n
    cur = target
    for idx in range(len(days) - 1, -1, -1):
        fwd, edges = days[idx]
        d = idx + 1
        for st, k2, add, S, dfr in edges:
            if k2 == cur and fwd[st] + add == (fwd_next_val(days, idx, cur, final, opt)):
                for i in S:
                    plan[i] = d
                for i in dfr:
                    plan[i] = L.DEF
                cur = st
                break
    return plan


def fwd_next_val(days, idx, key, final, opt):
    if idx + 1 < len(days):
        return days[idx + 1][0][key]
    return final[key]
