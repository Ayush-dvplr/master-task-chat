"""Prototype core: reference (lexicographic min-cost flow + exact tie pass) and wrong solvers.
Usage: core.py <solver> <inst.json> <out.json>"""
import heapq, json, sys
from collections import deque

DEPOTS = ["North", "South", "West", "East"]


class MCF:
    def __init__(self, n):
        self.n = n
        self.g = [[] for _ in range(n)]
        self.E = []  # [u, v, cap, cost]

    def add(self, u, v, cap, cost):
        i = len(self.E)
        self.E.append([u, v, cap, cost])
        self.E.append([v, u, 0, -cost])
        self.g[u].append(i)
        self.g[v].append(i + 1)
        return i

    def run(self, s, t, need):
        n, E, g = self.n, self.E, self.g
        pi = [0] * n
        flow = 0
        while flow < need:
            dist = [None] * n
            pe = [-1] * n
            dist[s] = 0
            pq = [(0, s)]
            while pq:
                d, u = heapq.heappop(pq)
                if d != dist[u]:
                    continue
                for ei in g[u]:
                    e = E[ei]
                    if e[2] > 0:
                        v = e[1]
                        nd = d + e[3] + pi[u] - pi[v]
                        if dist[v] is None or nd < dist[v]:
                            dist[v] = nd
                            pe[v] = ei
                            heapq.heappush(pq, (nd, v))
            if dist[t] is None:
                raise RuntimeError("infeasible")
            for v in range(n):
                if dist[v] is not None:
                    pi[v] += dist[v]
            f = need - flow
            v = t
            while v != s:
                e = E[pe[v]]
                f = min(f, e[2])
                v = e[0]
            v = t
            while v != s:
                ei = pe[v]
                E[ei][2] -= f
                E[ei ^ 1][2] += f
                v = E[ei][0]
            flow += f
        return flow

    def potentials(self):
        n, E = self.n, self.E
        pi = [0] * n
        inq = [True] * n
        q = deque(range(n))
        while q:
            u = q.popleft()
            inq[u] = False
            for ei in self.g[u]:
                e = E[ei]
                if e[2] > 0 and pi[u] + e[3] < pi[e[1]]:
                    pi[e[1]] = pi[u] + e[3]
                    if not inq[e[1]]:
                        inq[e[1]] = True
                        q.append(e[1])
        return pi


def dp(inst, d):
    return inst["dprice"][d] if "dprice" in inst else inst["price"]


def build(inst, buses, cap, feeder, K1, K2, KM, eps=0):
    S = inst["S"]
    n = len(buses)
    N = 2 + n + 4 * S + S
    m = MCF(N)
    pos = {}
    total = 0
    for i, b in enumerate(buses):
        bn = 2 + i
        m.add(0, bn, b["need"], 0)
        m.add(bn, 1, b["need"], K1 * b["w"])
        total += b["need"]
        di = DEPOTS.index(b["depot"])
        for s in range(b["a"], b["e"]):
            p = min(b["pub"].get(str(s), 0), b["rate"])
            ds = 2 + n + di * S + s
            c = K2 * dp(inst, b["depot"])[s] + eps * s
            e1 = m.add(bn, ds, p, c - KM) if p > 0 else None
            e2 = m.add(bn, ds, b["rate"] - p, c) if b["rate"] - p > 0 else None
            pos[(s, b["id"])] = (e1, e2, bn, ds)
    for di, d in enumerate(DEPOTS):
        for s in range(S):
            m.add(2 + n + di * S + s, 2 + n + 4 * S + s, cap[d][s], 0)
    for s in range(S):
        m.add(2 + n + 4 * S + s, 1, feeder[s], 0)
    return m, pos, total


def extract(m, pos):
    x = {}
    for (s, bid), (e1, e2, _, _) in pos.items():
        k = 0
        for e in (e1, e2):
            if e is not None:
                k += m.E[e ^ 1][2]
        if k:
            x[(bid, s)] = k
    return x


def tie_pass(m, pos):
    E = m.E
    pi = m.potentials()
    rc0 = [E[i][3] + pi[E[i][0]] - pi[E[i][1]] == 0 for i in range(len(E))]
    blocked = bytearray(len(E))
    for key in sorted(pos):
        e1, e2, u, v = pos[key]
        own = [e for e in (e1, e2) if e is not None]
        for e in own:
            blocked[e] = blocked[e ^ 1] = 1
        while True:
            fw = [e for e in own if E[e][2] > 0 and rc0[e]]
            if not fw:
                break
            # BFS v -> u over free unblocked edges
            prev = {v: -1}
            dq = deque([v])
            while dq and u not in prev:
                a = dq.popleft()
                for ei in m.g[a]:
                    if blocked[ei] or E[ei][2] <= 0 or not rc0[ei]:
                        continue
                    b = E[ei][1]
                    if b not in prev:
                        prev[b] = ei
                        dq.append(b)
            if u not in prev:
                break
            path = []
            c = u
            while c != v:
                path.append(prev[c])
                c = E[prev[c]][0]
            f = min([E[fw[0]][2]] + [E[ei][2] for ei in path])
            for ei in path + [fw[0]]:
                E[ei][2] -= f
                E[ei ^ 1][2] += f


def solve_flow(inst, buses=None, cap=None, feeder=None, tie=True, eps=False, km=1):
    buses = inst["buses"] if buses is None else buses
    cap = inst["cap"] if cap is None else cap
    feeder = inst["feeder"] if feeder is None else feeder
    if eps:
        m, pos, total = build(inst, buses, cap, feeder, 10 ** 24, 10 ** 14, 10 ** 8, eps=1)
    else:
        m, pos, total = build(inst, buses, cap, feeder, 10 ** 15, 10 ** 6, km)
    m.run(0, 1, total)
    if tie:
        tie_pass(m, pos)
    return extract(m, pos)


def chunks(b, price):
    out = []
    for s in range(b["a"], b["e"]):
        p = min(b["pub"].get(str(s), 0), b["rate"])
        if p:
            out.append(((price[s], 0, s), s, p))
        if b["rate"] - p:
            out.append(((price[s], 1, s), s, b["rate"] - p))
    out.sort()
    return out


def greedy(inst, order):
    price = inst["price"]
    capr = {d: list(inst["cap"][d]) for d in DEPOTS}
    fr = list(inst["feeder"])
    x = {}
    for b in sorted(inst["buses"], key=order):
        rem = b["need"]
        for _, s, k in chunks(b, price):
            if rem <= 0:
                break
            q = min(k, rem, capr[b["depot"]][s], fr[s])
            if q > 0:
                x[(b["id"], s)] = x.get((b["id"], s), 0) + q
                capr[b["depot"]][s] -= q
                fr[s] -= q
                rem -= q
    return x


def greedy_swap(inst):
    x = greedy(inst, lambda b: b["id"])
    price = inst["price"]
    load = {d: [0] * inst["S"] for d in DEPOTS}
    for (bid, s), k in x.items():
        pass
    byid = {b["id"]: b for b in inst["buses"]}
    for (bid, s), k in x.items():
        load[byid[bid]["depot"]][s] += k
    changed = True
    while changed:
        changed = False
        for b in inst["buses"]:
            used = sorted([s for (bb, s) in x if bb == b["id"]], key=lambda s: -price[s])
            for s_hi in used:
                for s_lo in sorted(range(b["a"], b["e"]), key=lambda s: (price[s], s)):
                    if price[s_lo] >= price[s_hi]:
                        break
                    room = min(b["rate"] - x.get((b["id"], s_lo), 0),
                               inst["cap"][b["depot"]][s_lo] - load[b["depot"]][s_lo],
                               inst["feeder"][s_lo] - sum(load[d][s_lo] for d in DEPOTS),
                               x.get((b["id"], s_hi), 0))
                    if room > 0:
                        x[(b["id"], s_lo)] = x.get((b["id"], s_lo), 0) + room
                        x[(b["id"], s_hi)] -= room
                        load[b["depot"]][s_lo] += room
                        load[b["depot"]][s_hi] -= room
                        if x[(b["id"], s_hi)] == 0:
                            del x[(b["id"], s_hi)]
                        changed = True
    return x


def per_depot(inst, mode):
    S = inst["S"]
    x = {}
    fr = list(inst["feeder"])
    for d in DEPOTS:
        bs = [b for b in inst["buses"] if b["depot"] == d]
        if mode == "prorata":
            tot = [sum(inst["cap"][dd][s] for dd in DEPOTS) for s in range(S)]
            share = [inst["feeder"][s] * inst["cap"][d][s] // tot[s] for s in range(S)]
        else:
            share = fr
        capd = {dd: [0] * S for dd in DEPOTS}
        capd[d] = [min(inst["cap"][d][s], share[s]) for s in range(S)]
        xd = solve_flow(inst, bs, capd, share)
        for (bid, s), k in xd.items():
            fr[s] -= k
        x.update(xd)
    return x


def careful_resolve(inst):
    """B4: fix each (slot, bus) in order at its largest value keeping terms 1-3, by re-solving."""
    buses = inst["buses"]
    S = inst["S"]
    fixed = {}
    keys = sorted((s, b["id"]) for b in buses for s in range(b["a"], b["e"]))
    for key in keys:
        bm = {}
        for b in buses:
            bm[b["id"]] = b
        m, pos, total = build(inst, buses, inst["cap"], inst["feeder"], 10 ** 24, 10 ** 15, 10 ** 9)
        for k2, val in fixed.items():
            e1, e2, _, _ = pos[k2]
            for e in (e1, e2):
                if e is not None:
                    m.E[e][3] += 0  # placeholder for clarity
        # cost tweak: reward the current key, force fixed ones by bounding caps
        for k2, val in fixed.items():
            e1, e2, u, v = pos[k2]
            rest = val
            for e in (e1, e2):
                if e is not None:
                    c = m.E[e][2]
                    m.E[e][2] = min(c, rest)
                    rest -= m.E[e][2]
        e1, e2, _, _ = pos[key]
        for e in (e1, e2):
            if e is not None:
                m.E[e][3] -= 1
                m.E[e ^ 1][3] += 1
        try:
            m.run(0, 1, total)
        except RuntimeError:
            return None
        xx = extract(m, pos)
        fixed[key] = xx.get((key[1], key[0]), 0)
    return {(bid, s): k for (s, bid), k in fixed.items() if k}


def families(inst, x):
    S = inst["S"]
    byid = {b["id"]: b for b in inst["buses"]}
    audit = {}
    for b in inst["buses"]:
        row = tuple(sorted((s, k) for (bid, s), k in x.items() if bid == b["id"]))
        audit[b["id"]] = row
    fam = {"audit": json.dumps(sorted(audit.items()))}
    for d in DEPOTS:
        load = [0] * S
        for (bid, s), k in x.items():
            if byid[bid]["depot"] == d:
                load[s] += k
        rows = {bid: audit[bid] for bid in audit if byid[bid]["depot"] == d}
        dc = sum(k * dp(inst, d)[s] for (bid, s), k in x.items() if byid[bid]["depot"] == d)
        fam["region_" + d] = json.dumps([load, dc, sorted(rows.items())])
    for cls, w in (("commercial", 1), ("public", 4)):
        rows = {bid: audit[bid] for bid in audit if byid[bid]["w"] == w}
        sc = sum(k * dp(inst, byid[bid]["depot"])[s] for (bid, s), k in x.items() if byid[bid]["w"] == w)
        fam["segment_" + cls] = json.dumps([sc, sorted(rows.items())])
    load = [0] * S
    unmet = 0
    cost = 0
    moved = 0
    for (bid, s), k in x.items():
        load[s] += k
        cost += k * dp(inst, byid[bid]["depot"])[s]
    for b in inst["buses"]:
        got = sum(k for (bid, s), k in x.items() if bid == b["id"])
        unmet += b["w"] * (b["need"] - got)
        for s, p in b["pub"].items():
            moved += max(0, min(p, b["rate"]) - x.get((b["id"], int(s)), 0))
    fam["summary"] = json.dumps([unmet, cost, moved, load])
    obj = [unmet, cost, moved]
    return fam, obj


def check_feasible(inst, x):
    S = inst["S"]
    byid = {b["id"]: b for b in inst["buses"]}
    load = {d: [0] * S for d in DEPOTS}
    got = {}
    for (bid, s), k in x.items():
        b = byid[bid]
        assert b["a"] <= s < b["e"] and 0 < k <= b["rate"], (bid, s, k)
        load[b["depot"]][s] += k
        got[bid] = got.get(bid, 0) + k
    for d in DEPOTS:
        for s in range(S):
            assert load[d][s] <= inst["cap"][d][s], (d, s)
    for s in range(S):
        assert sum(load[d][s] for d in DEPOTS) <= inst["feeder"][s], s
    for b in inst["buses"]:
        assert got.get(b["id"], 0) <= b["need"]
    binds_f = sum(1 for s in range(S) if sum(load[d][s] for d in DEPOTS) == inst["feeder"][s])
    binds_c = sum(1 for d in DEPOTS for s in range(S) if load[d][s] == inst["cap"][d][s] and load[d][s] > 0)
    return binds_f, binds_c


def split_exact(inst):
    """Split into independent parts (buses sharing a depot slot or a feeder slot), solve each exactly."""
    bs = inst["buses"]
    par = list(range(len(bs)))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    owner = {}
    for i, b in enumerate(bs):
        for s in range(b["a"], b["e"]):
            if s in owner:
                par[f(i)] = f(owner[s])
            else:
                owner[s] = i
    parts = {}
    for i in range(len(bs)):
        parts.setdefault(f(i), []).append(bs[i])
    sys.stderr.write("parts=%d\n" % len(parts))
    x = {}
    for part in parts.values():
        x.update(solve_flow(inst, part, tie=False))
    return x


def flow_post(inst):
    """B3: plain optimum, then one greedy pass moving a bus's kWh earlier at equal price where room is left."""
    x = solve_flow(inst, tie=False)
    S = inst["S"]
    price = inst["price"]
    byid = {b["id"]: b for b in inst["buses"]}
    load = {d: [0] * S for d in DEPOTS}
    for (bid, s), k in x.items():
        load[byid[bid]["depot"]][s] += k
    for s in range(S):
        for b in sorted(inst["buses"], key=lambda b: b["id"]):
            if not (b["a"] <= s < b["e"]):
                continue
            for s2 in range(b["e"] - 1, s, -1):
                if price[s2] != price[s] or x.get((b["id"], s2), 0) == 0:
                    continue
                room = min(b["rate"] - x.get((b["id"], s), 0),
                           inst["cap"][b["depot"]][s] - load[b["depot"]][s],
                           inst["feeder"][s] - sum(load[d][s] for d in DEPOTS), x[(b["id"], s2)])
                if room > 0:
                    x[(b["id"], s)] = x.get((b["id"], s), 0) + room
                    x[(b["id"], s2)] -= room
                    load[b["depot"]][s] += room
                    load[b["depot"]][s2] -= room
                    if not x[(b["id"], s2)]:
                        del x[(b["id"], s2)]
    return x


def flow_bigint(inst, sign=-1):
    """Careful exact: whole order folded into one big-integer arc cost (tie-break as base-61 digits)."""
    keys = sorted((s, b["id"]) for b in inst["buses"] for s in range(b["a"], b["e"]))
    P = len(keys)
    BIG = 61 ** P
    m, pos, total = build(inst, inst["buses"], inst["cap"], inst["feeder"], 10 ** 15 * BIG, 10 ** 6 * BIG, BIG)
    for i, key in enumerate(keys):
        t = 61 ** (P - 1 - i)
        for e in pos[key][:2]:
            if e is not None:
                m.E[e][3] += sign * t
                m.E[e ^ 1][3] -= sign * t
    m.run(0, 1, total)
    return extract(m, pos)


SOLVERS = {
    "flow_bigint": flow_bigint,
    "bigint_min": lambda i: flow_bigint(i, sign=1),
    "split_exact": split_exact,
    "flow_post": flow_post,
    "ref": lambda i: solve_flow(i),
    "greedy_id": lambda i: greedy(i, lambda b: b["id"]),
    "greedy_edf": lambda i: greedy(i, lambda b: (b["e"], b["id"])),
    "greedy_class": lambda i: greedy(i, lambda b: (-b["w"], b["id"])),
    "greedy_swap": greedy_swap,
    "depot_prorata": lambda i: per_depot(i, "prorata"),
    "depot_priority": lambda i: per_depot(i, "priority"),
    "flow_plain": lambda i: solve_flow(i, tie=False),
    "flow_eps": lambda i: solve_flow(i, tie=False, eps=True),
    "careful_resolve": careful_resolve,
    "ref_nofeed": lambda i: solve_flow(i, feeder=[10 ** 9] * i["S"]),
    "ref_nocab": lambda i: solve_flow(i, cap={d: [10 ** 9] * i["S"] for d in DEPOTS}),
    "ref_noterm3": lambda i: solve_flow(i, km=0),
}

if __name__ == "__main__":
    import time
    inst = json.load(open(sys.argv[2]))
    t0 = time.time()
    x = SOLVERS[sys.argv[1]](inst)
    dt = time.time() - t0
    fam, obj = families(inst, x)
    try:
        bf, bc = check_feasible(inst, x)
    except AssertionError as err:
        bf, bc = "infeasible", str(err)
    json.dump({"fam": fam, "obj": obj, "sec": round(dt, 2), "bind_feeder": bf, "bind_cap": bc},
              open(sys.argv[3], "w"))
