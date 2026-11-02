"""Generic solvers for the kill test. Each takes a reference project dict and
returns (cost, sorted link ids) or None."""
from __future__ import annotations

import heapq
import itertools
from collections import deque

import ref


def _adj(proj):
    adj = [[] for _ in range(proj["n"] + 1)]
    for r, (lid, lo, hi, cost) in enumerate(proj["links"]):
        adj[lo].append((hi, cost, r))
        adj[hi].append((lo, cost, r))
    return adj


def _cost(proj, rs):
    lit = {0} | set(proj["cold"])
    for r in rs:
        lit.update(proj["links"][r][1:3])
    return sum(proj["links"][r][3] for r in rs) + sum(proj["charge"][v] for v in lit)


def _out(proj, rs):
    return _cost(proj, rs), sorted(proj["links"][r][0] for r in rs)


def _prune(proj, rs):
    """MST of the chosen subgraph (by cost), then drop relay leaves repeatedly."""
    rs = sorted(rs, key=lambda r: proj["links"][r][3])
    root = list(range(proj["n"] + 1))

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    keep = []
    for r in rs:
        a, b = proj["links"][r][1:3]
        if find(a) != find(b):
            root[find(a)] = find(b)
            keep.append(r)
    need = {0} | set(proj["cold"])
    while True:
        deg = {}
        for r in keep:
            for x in proj["links"][r][1:3]:
                deg[x] = deg.get(x, 0) + 1
        drop = [r for r in keep if any(deg[x] == 1 and x not in need for x in proj["links"][r][1:3])]
        if not drop:
            return keep
        keep = [r for r in keep if r not in drop]


def _dijkstra(proj, adj, src, node_weight=True):
    dist = {src: 0}
    prev = {}
    heap = [(0, src)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for u, c, r in adj[v]:
            nd = d + c + (proj["charge"][u] if node_weight else 0)
            if nd < dist.get(u, float("inf")):
                dist[u] = nd
                prev[u] = (v, r)
                heapq.heappush(heap, (nd, u))
    return dist, prev


def _path(prev, src, dst):
    rs = []
    while dst != src:
        dst, r = prev[dst]
        rs.append(r)
    return rs


def kmb(proj):
    adj = _adj(proj)
    terms = [0] + sorted(proj["cold"])
    info = {t: _dijkstra(proj, adj, t) for t in terms}
    pairs = sorted((info[a][0][b], a, b) for a, b in itertools.combinations(terms, 2) if b in info[a][0])
    root = {t: t for t in terms}

    def find(x):
        while root[x] != x:
            x = root[x]
        return x

    rs = set()
    for _d, a, b in pairs:
        if find(a) != find(b):
            root[find(a)] = find(b)
            rs.update(_path(info[a][1], a, b))
    return _out(proj, _prune(proj, rs))


def sph(proj, node_weight=True):
    adj = _adj(proj)
    tree = {0}
    rs = set()
    left = set(proj["cold"])
    while left:
        dist = {v: 0 for v in tree}
        prev = {}
        heap = [(0, v) for v in tree]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist[v]:
                continue
            for u, c, r in adj[v]:
                nd = d + c + ((0 if u in tree else proj["charge"][u]) if node_weight else 0)
                if nd < dist.get(u, float("inf")):
                    dist[u] = nd
                    prev[u] = (v, r)
                    heapq.heappush(heap, (nd, u))
        t = min(left, key=lambda x: (dist.get(x, float("inf")), x))
        v = t
        while v not in tree:
            v2, r = prev[v]
            rs.add(r)
            tree.add(v)
            v = v2
        left -= tree
    return _out(proj, _prune(proj, rs))


def greedy(proj):
    """Nearest-terminal growth on link cost alone."""
    return sph(proj, node_weight=False)


def dw_global(proj):
    m = len(proj["links"])
    unit = 1 << m
    verts = list(range(proj["n"] + 1))
    elist = [(lo, hi, c * unit + (1 << (m - 1 - r)), r) for r, (_l, lo, hi, c) in enumerate(proj["links"])]
    wt = {v: (0 if v == 0 else proj["charge"][v] * unit) for v in verts}
    score, rs = ref._dw(verts, elist, 0, sorted(proj["cold"]), wt)
    return _out(proj, rs)


def naive_subset(proj):
    """Every relay subset by size; spanning tree of depot + cold rooms + subset."""
    relays = [v for v in range(1, proj["n"] + 1) if v not in proj["cold"]]
    best = None
    for k in range(len(relays) + 1):
        for extra in itertools.combinations(relays, k):
            keep = {0} | set(proj["cold"]) | set(extra)
            rs = [r for r, (_l, lo, hi, _c) in enumerate(proj["links"]) if lo in keep and hi in keep]
            tree = _prune(proj, rs)
            seen = {0}
            for r in tree:
                seen.update(proj["links"][r][1:3])
            if not set(proj["cold"]) <= seen:
                continue
            got = _out(proj, tree)
            if best is None or got < best:
                best = got
    return best


def _reorder(proj, order):
    """Same project with positions renumbered by `order` (order[0] == 0)."""
    pos = {v: k for k, v in enumerate(order)}
    links = sorted((lid, min(pos[a], pos[b]), max(pos[a], pos[b]), c) for lid, a, b, c in proj["links"])
    return {**proj, "charge": [proj["charge"][v] for v in order], "cold": {pos[c] for c in proj["cold"]}, "links": links}


def frontier(tt, proj, order=None):
    """Template sweep with the window set from the data (largest non-depot span)."""
    p = proj if order is None else _reorder(proj, order)
    width = max([1] + [hi - lo for _l, lo, hi, _c in p["links"] if lo])
    saved = tt.WIDTH
    tt.WIDTH = width
    try:
        found = tt._optimum(p)
    finally:
        tt.WIDTH = saved
    return None if found is None else (found[0], found[2])


def bfs_order(proj):
    adj = _adj(proj)
    seen = [0]
    q = deque([0])
    mark = {0}
    while q:
        v = q.popleft()
        for u, _c, _r in sorted(adj[v]):
            if u not in mark:
                mark.add(u)
                seen.append(u)
                q.append(u)
    return seen + [v for v in range(proj["n"] + 1) if v not in mark]


def frontier_lastuse(proj, order):
    """Exact sweep over `order` (order[0] == 0); a site leaves the state after its last neighbour."""
    step = {v: i for i, v in enumerate(order)}
    nbr = {v: [] for v in order}
    for lid, a, b, c in proj["links"]:
        nbr[a].append((b, c, lid))
        nbr[b].append((a, c, lid))
    last = {v: max([step[v]] + [step[u] for u, _c, _l in nbr[v]]) for v in order}
    charge, cold = proj["charge"], proj["cold"]
    layers = [{(): (charge[0], None, ())}]
    for i, v in enumerate(order[1:], 1):
        arriving = [(u, c, lid) for u, c, lid in nbr[v] if step[u] < i]
        layer = {}
        for key, (cost, _b, _t) in layers[-1].items():
            tags = dict(key)
            branches = [] if v in cold else [(dict(tags), cost, ())]
            fresh = max([0, *tags.values()]) + 1
            grown = [({**tags, v: fresh}, cost + charge[v], ())]
            for lo, link_cost, lid in arriving:
                if lo != 0 and lo not in tags:
                    continue
                extra = []
                for current, spent, took in grown:
                    left = 0 if lo == 0 else current[lo]
                    right = current[v]
                    if left == right:
                        continue
                    keep, drop = min(left, right), max(left, right)
                    joined = {s: (keep if t == drop else t) for s, t in current.items()}
                    extra.append((joined, spent + link_cost, took + (lid,)))
                grown += extra
            branches += grown
            for current, spent, took in branches:
                dead = False
                for s in [s for s in current if last[s] <= i]:
                    tag = current.pop(s)
                    if tag != 0 and tag not in current.values():
                        dead = True
                        break
                if dead:
                    continue
                names = {0: 0}
                nxt = []
                for s, t in sorted(current.items()):
                    names.setdefault(t, len(names))
                    nxt.append((s, names[t]))
                nxt = tuple(nxt)
                held = layer.get(nxt)
                if held is None or spent < held[0]:
                    layer[nxt] = (spent, key, took)
        layers.append(layer)
    ends = [(e[0], k) for k, e in layers[-1].items() if all(t == 0 for _s, t in k)]
    if not ends:
        return None
    best, key = min(ends)
    chosen = []
    for i in range(len(order) - 1, 0, -1):
        _c, back, took = layers[i][key]
        chosen += took
        key = back
    return best, sorted(chosen)


def greedy_order(proj):
    """Next site = the one that leaves the fewest sites still waiting on a neighbour."""
    adj = _adj(proj)
    nb = [set(u for u, _c, _r in adj[v]) for v in range(proj["n"] + 1)]
    seen = {0}
    order = [0]
    while len(order) < proj["n"] + 1:
        cand = {u for v in seen for u in nb[v]} - seen or set(range(proj["n"] + 1)) - seen

        def score(u):
            s2 = seen | {u}
            return (sum(1 for x in s2 if nb[x] - s2), len(nb[u] - s2), u)
        u = min(cand, key=score)
        seen.add(u)
        order.append(u)
    return order
