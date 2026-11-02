"""Prototype core model for outage-window-replan (kill test only, not shipped).

Region instance:
  H: horizon days 1..H
  cap[type]: list len H+2 (index = day), crews available
  factor: list len H+2 (index = day), load band factor 1..3
  blackout: set of days on which no outage may start
  reqs: list (sorted by asset id) of dict id,type,crews,dur,e,l,w,pub (pub start or None)
  incompat: list of (i, j) index pairs (no common day out)
  prec: list of (i, j): j starts no earlier than the day after i finishes; i deferred => j deferred
Objective (lexicographic): total cost, moved count, start vector in asset-id order (deferred = H+1).
"""
import time

DEFER_FACTOR = 4


class Inst:
    def __init__(self, d):
        self.H = d["H"]
        self.cap = d["cap"]
        self.factor = d["factor"]
        self.blackout = set(d["blackout"])
        self.reqs = d["reqs"]
        self.incompat = d["incompat"]
        self.prec = d["prec"]
        n = len(self.reqs)
        self.n = n
        self.DEF = self.H + 1
        self.inc_of = [[] for _ in range(n)]
        for i, j in self.incompat:
            self.inc_of[i].append(j)
            self.inc_of[j].append(i)
        self.pred_of = [[] for _ in range(n)]
        self.succ_of = [[] for _ in range(n)]
        for i, j in self.prec:
            self.pred_of[j].append(i)
            self.succ_of[i].append(j)
        # static options: starts inside window, not blackout, static capacity ok
        self.opts = []
        self.cost = []
        for r in self.reqs:
            o = []
            c = {}
            for s in range(r["e"], r["l"] - r["dur"] + 2):
                if s in self.blackout:
                    continue
                if all(self.cap[r["type"]][d] >= r["crews"] for d in range(s, s + r["dur"])):
                    o.append(s)
                    c[s] = r["w"] * sum(self.factor[d] for d in range(s, s + r["dur"]))
            o.append(self.DEF)
            c[self.DEF] = r["w"] * r["dur"] * DEFER_FACTOR
            self.opts.append(o)
            self.cost.append(c)

    def moved(self, i, s):
        p = self.reqs[i]["pub"]
        return 0 if p is None or p == s else 1

    def objective(self, plan):
        c = sum(self.cost[i][plan[i]] for i in range(self.n))
        m = sum(self.moved(i, plan[i]) for i in range(self.n))
        return (c, m, tuple(plan))

    def feasible(self, plan):
        H = self.H
        use = {t: [0] * (H + 2) for t in self.cap}
        for i, s in enumerate(plan):
            r = self.reqs[i]
            if s == self.DEF:
                continue
            if s not in self.cost[i]:
                return False
            for d in range(s, s + r["dur"]):
                use[r["type"]][d] += r["crews"]
                if use[r["type"]][d] > self.cap[r["type"]][d]:
                    return False
        for i, j in self.incompat:
            a, b = plan[i], plan[j]
            if a != self.DEF and b != self.DEF:
                if a < b + self.reqs[j]["dur"] and b < a + self.reqs[i]["dur"]:
                    return False
        for i, j in self.prec:
            a, b = plan[i], plan[j]
            if a == self.DEF and b != self.DEF:
                return False
            if a != self.DEF and b != self.DEF and b < a + self.reqs[i]["dur"]:
                return False
        return True


class State:
    """Incremental assignment state for search over a subset of indices."""

    def __init__(self, inst):
        self.I = inst
        self.use = {t: [0] * (inst.H + 2) for t in inst.cap}
        self.asg = {}

    def ok(self, i, s):
        I = self.I
        r = I.reqs[i]
        if s == I.DEF:
            for j in I.succ_of[i]:
                if j in self.asg and self.asg[j] != I.DEF:
                    return False
            return True
        cap = I.cap[r["type"]]
        use = self.use[r["type"]]
        for d in range(s, s + r["dur"]):
            if use[d] + r["crews"] > cap[d]:
                return False
        for j in I.inc_of[i]:
            b = self.asg.get(j)
            if b is not None and b != I.DEF:
                if s < b + I.reqs[j]["dur"] and b < s + r["dur"]:
                    return False
        for p in I.pred_of[i]:
            a = self.asg.get(p)
            if a is not None:
                if a == I.DEF:
                    return False
                if s < a + I.reqs[p]["dur"]:
                    return False
        for q in I.succ_of[i]:
            b = self.asg.get(q)
            if b is not None and b != I.DEF and b < s + r["dur"]:
                return False
        return True

    def put(self, i, s):
        self.asg[i] = s
        if s != self.I.DEF:
            r = self.I.reqs[i]
            u = self.use[r["type"]]
            for d in range(s, s + r["dur"]):
                u[d] += r["crews"]

    def take(self, i):
        s = self.asg.pop(i)
        if s != self.I.DEF:
            r = self.I.reqs[i]
            u = self.use[r["type"]]
            for d in range(s, s + r["dur"]):
                u[d] -= r["crews"]


def greedy_pick(I, st, i):
    best = None
    for s in I.opts[i]:
        if st.ok(i, s):
            k = (I.cost[i][s], I.moved(i, s), s)
            if best is None or k < best[0]:
                best = (k, s)
    return best[1] if best else I.DEF


def force_defer(I, st, i):
    for q in I.succ_of[i]:
        if q in st.asg and st.asg[q] != I.DEF:
            st.take(q)
            force_defer(I, st, q)
            st.put(q, I.DEF)


def greedy(I, order):
    st = State(I)
    for i in order:
        s = greedy_pick(I, st, i)
        if s == I.DEF:
            force_defer(I, st, i)
        st.put(i, s)
    plan = [st.asg[i] for i in range(I.n)]
    if not I.feasible(plan):
        # precedence fallout: defer successors of deferred
        return None
    return plan


def components(I, idx=None):
    n = I.n
    par = list(range(n))

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def u(a, b):
        a, b = f(a), f(b)
        if a != b:
            par[a] = b

    rs = I.reqs
    for a in range(n):
        for b in range(a + 1, n):
            if rs[a]["type"] == rs[b]["type"] and rs[a]["e"] <= rs[b]["l"] and rs[b]["e"] <= rs[a]["l"]:
                u(a, b)
    for a, b in I.incompat:
        u(a, b)
    for a, b in I.prec:
        u(a, b)
    g = {}
    for a in range(n):
        g.setdefault(f(a), []).append(a)
    return sorted(g.values())


class Timeout(Exception):
    pass


def bb(I, idx, order, init=None, deadline=None, strict=False, target=None, counter=None):
    """Branch and bound over indices idx in variable order `order`.
    strict=False: prune LB >= best (keeps first optimum found in this order)
    target: (cost, moved) -> find first complete assignment in this order with value == target,
            prune LB > target.
    Returns (value(cost,moved), assignment dict)."""
    st = State(I)
    best = [init[0] if init else None, init[1] if init else None]
    nodes = [0]
    rem_set = set(idx)

    def lb():
        c = 0
        m = 0
        for i in rem_set:
            mc = None
            mm = 0
            for s in I.opts[i]:
                if st.ok(i, s):
                    cc = I.cost[i][s]
                    mv = I.moved(i, s)
                    if mc is None or cc < mc or (cc == mc and mv < mm):
                        mc, mm = cc, mv
            if mc is None:
                return None
            c += mc
            m += mm
        return (c, m)

    def rec(k, cc, cm):
        nodes[0] += 1
        if deadline is not None and (nodes[0] & 255) == 0 and time.time() > deadline:
            raise Timeout()
        if k == len(order):
            v = (cc, cm)
            if target is not None:
                if v == target:
                    best[0] = v
                    best[1] = dict(st.asg)
                    return True
                return False
            if best[0] is None or v < best[0]:
                best[0] = v
                best[1] = dict(st.asg)
            return False
        L = lb()
        if L is None:
            return False
        L = (cc + L[0], cm + L[1])
        if target is not None:
            if L > target:
                return False
        elif best[0] is not None and (L >= best[0] if not strict else L > best[0]):
            return False
        i = order[k]
        rem_set.discard(i)
        for s in I.opts[i]:
            if st.ok(i, s):
                st.put(i, s)
                stop = rec(k + 1, cc + I.cost[i][s], cm + I.moved(i, s))
                st.take(i)
                if stop:
                    rem_set.add(i)
                    return True
        rem_set.add(i)
        return False

    try:
        rec(0, 0, 0)
        timed_out = False
    except Timeout:
        timed_out = True
    if counter is not None:
        counter[0] += nodes[0]
    return best[0], best[1], timed_out


def order_heur(I, idx):
    return sorted(idx, key=lambda i: (-I.reqs[i]["w"] * I.reqs[i]["dur"], i))


def order_time(I, idx):
    return sorted(idx, key=lambda i: (I.reqs[i]["e"], I.reqs[i]["l"], i))


def reference(I, counter=None):
    plan = [None] * I.n
    for comp in components(I):
        v, a, _ = bb(I, comp, order_heur(I, comp), counter=counter)
        v2, a2, _ = bb(I, comp, sorted(comp), target=v, counter=counter)
        assert v2 == v, (v, v2)
        for i in comp:
            plan[i] = a2[i]
    return plan
