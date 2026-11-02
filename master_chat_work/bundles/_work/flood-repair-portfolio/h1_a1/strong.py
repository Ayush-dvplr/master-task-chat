"""Strong plain exact solvers for the kill table (run in Docker only).

Each solver takes (n, adj bitmasks, encoded weights) and returns the chosen bitmask.
Weights are encoded benefit * 2**n + tie bit, so the maximum is unique.
"""
import time


def bits(m):
    while m:
        low = m & -m
        yield low.bit_length() - 1
        m ^= low


def min_fill_order(n, adj):
    graph = list(adj)
    alive = (1 << n) - 1
    order = []
    while alive:
        pick, score = -1, None
        for v in bits(alive):
            around = graph[v] & alive
            missing = 0
            for u in bits(around):
                missing += bin(around & ~graph[u] & ~(1 << u)).count("1")
            key = (missing, bin(around).count("1"), v)
            if score is None or key < score:
                pick, score = v, key
        around = graph[pick] & alive
        for u in bits(around):
            graph[u] |= around & ~(1 << u)
        alive &= ~(1 << pick)
        order.append(pick)
    return order


def min_degree_order(n, adj):
    graph = list(adj)
    alive = (1 << n) - 1
    order = []
    while alive:
        pick = min(bits(alive), key=lambda v: (bin(graph[v] & alive).count("1"), v))
        around = graph[pick] & alive
        for u in bits(around):
            graph[u] |= around & ~(1 << u)
        alive &= ~(1 << pick)
        order.append(pick)
    return order


def sweep(n, adj, w, order):
    """Frontier DP over a linear order; states keyed by chosen frontier subset."""
    pos = [0] * n
    for i, v in enumerate(order):
        pos[v] = i
    last = [0] * n
    for v in range(n):
        last[v] = max([pos[u] for u in bits(adj[v])] + [pos[v]])
    dying = [0] * n
    for v in range(n):
        dying[last[v]] |= 1 << v
    states = {0: (0, 0)}
    for i, v in enumerate(order):
        vb = 1 << v
        nb = adj[v]
        drop = ~dying[i]
        nxt = {}
        for key, (score, chosen) in states.items():
            k = key & drop
            old = nxt.get(k)
            if old is None or score > old[0]:
                nxt[k] = (score, chosen)
            if not key & nb:
                k = (key | vb) & drop
                s = score + w[v]
                old = nxt.get(k)
                if old is None or s > old[0]:
                    nxt[k] = (s, chosen | vb)
        states = nxt
    return max(states.values())[1]


def width(n, adj, order):
    pos = [0] * n
    for i, v in enumerate(order):
        pos[v] = i
    live = 0
    best = 0
    born = 0
    for i, v in enumerate(order):
        born |= 1 << v
        live = 0
        for u in bits(born):
            if any(pos[x] > i for x in bits(adj[u])):
                live += 1
        best = max(best, live)
    return best


def components(n, adj):
    seen = 0
    parts = []
    for s in range(n):
        if seen >> s & 1:
            continue
        comp = 1 << s
        grow = comp
        while grow:
            nxt = 0
            for v in bits(grow):
                nxt |= adj[v]
            grow = nxt & ~comp
            comp |= grow
        seen |= comp
        parts.append(comp)
    return parts


def solve(kind, n, adj, w):
    t0 = time.perf_counter()
    chosen = 0
    for comp in components(n, adj):
        verts = list(bits(comp))
        idx = {v: i for i, v in enumerate(verts)}
        sub = [0] * len(verts)
        for v in verts:
            for u in bits(adj[v] & comp):
                sub[idx[v]] |= 1 << idx[u]
        sw = [w[v] for v in verts]
        m = len(verts)
        if kind == "sweep_mf":
            order = min_fill_order(m, sub)
        elif kind == "sweep_mfrev":
            order = min_fill_order(m, sub)[::-1]
        elif kind == "sweep_md":
            order = min_degree_order(m, sub)
        elif kind == "sweep_id":
            order = list(range(m))
        else:
            raise SystemExit("unknown kind")
        t1 = time.perf_counter()
        got = sweep(m, sub, sw, order)
        for i in bits(got):
            chosen |= 1 << verts[i]
    return chosen, time.perf_counter() - t0


def ve(n, adj, w, order):
    """Variable elimination over a given order; tables over independent subsets of each scope.

    Scores are encoded ints (unique maximum), each table entry keeps (score, chosen mask).
    """
    graph = list(adj)
    alive = (1 << n) - 1
    steps = []
    for v in order:
        around = graph[v] & alive
        for u in bits(around):
            graph[u] |= around & ~(1 << u)
        alive &= ~(1 << v)
        steps.append((v, around))
    place = [0] * n
    for k, v in enumerate(order):
        place[v] = k
    inbox = [[] for _ in range(n)]
    total, chosen = 0, 0
    for v, scope in steps:
        members = list(bits(scope))
        subsets = [0]
        for u in members:
            nu = adj[u]
            subsets += [s | (1 << u) for s in subsets if not s & nu]
        msgs = inbox[v]
        vb = 1 << v
        nv = adj[v]
        wv = w[v]
        table = {}
        for s in subsets:
            sc, ch = 0, 0
            for mask, msg in msgs:
                a, b = msg[s & mask]
                sc += a
                ch |= b
            if not s & nv:
                sc2, ch2 = wv, vb
                sv = s | vb
                for mask, msg in msgs:
                    a, b = msg[sv & mask]
                    sc2 += a
                    ch2 |= b
                if sc2 > sc:
                    sc, ch = sc2, ch2
            table[s] = (sc, ch)
        if members:
            inbox[min(members, key=place.__getitem__)].append((scope, table))
        else:
            total += table[0][0]
            chosen |= table[0][1]
    return chosen


def solve_ve(kind, n, adj, w):
    t0 = time.perf_counter()
    chosen = 0
    t_order = 0.0
    for comp in components(n, adj):
        verts = list(bits(comp))
        idx = {v: i for i, v in enumerate(verts)}
        sub = [0] * len(verts)
        for v in verts:
            for u in bits(adj[v] & comp):
                sub[idx[v]] |= 1 << idx[u]
        m = len(verts)
        ta = time.perf_counter()
        order = min_fill_order(m, sub) if kind == "ve_mf" else min_degree_order(m, sub)
        t_order += time.perf_counter() - ta
        got = ve(m, sub, [w[v] for v in verts], order)
        for i in bits(got):
            chosen |= 1 << verts[i]
    return chosen, time.perf_counter() - t0, t_order
