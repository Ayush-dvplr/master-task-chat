"""Prototype exact reference: block decomposition at cut sites + node-weighted
Dreyfus-Wagner inside each block, scored cost*2^m + link bit (tie rule)."""
from __future__ import annotations

import heapq

INF = float("inf")


def _blocks(n, adj):
    """Biconnected blocks reachable from 0, children before parents: [(top, [edge idx])]."""
    disc = [-1] * (n + 1)
    low = [0] * (n + 1)
    disc[0] = low[0] = 0
    clock = 1
    edges, out = [], []
    stack = [(0, -1, iter(adj[0]))]
    while stack:
        v, pe, nbrs = stack[-1]
        moved = False
        for u, _w, r in nbrs:
            if r == pe:
                continue
            if disc[u] == -1:
                edges.append(r)
                disc[u] = low[u] = clock
                clock += 1
                stack.append((u, r, iter(adj[u])))
                moved = True
                break
            if disc[u] < disc[v]:
                edges.append(r)
                low[v] = min(low[v], disc[u])
        if moved:
            continue
        stack.pop()
        if stack:
            p = stack[-1][0]
            low[p] = min(low[p], low[v])
            if low[v] >= disc[p]:
                blk = []
                while True:
                    r = edges.pop()
                    blk.append(r)
                    if r == pe:
                        break
                out.append((p, blk))
    return out, disc


def _dw(verts, elist, root, terms, wt):
    """Node-weighted Steiner tree in one block: (score, set of edge idx)."""
    idx = {v: i for i, v in enumerate(verts)}
    N = len(verts)
    adj = [[] for _ in range(N)]
    for a, b, w, r in elist:
        adj[idx[a]].append((idx[b], w, r))
        adj[idx[b]].append((idx[a], w, r))
    w_of = [wt[v] for v in verts]
    k = len(terms)
    full = (1 << k) - 1
    dp = [[INF] * N for _ in range(full + 1)]
    back = [[None] * N for _ in range(full + 1)]
    for i, t in enumerate(terms):
        dp[1 << i][idx[t]] = w_of[idx[t]]
        back[1 << i][idx[t]] = ("leaf",)
    for S in range(1, full + 1):
        row = dp[S]
        brow = back[S]
        if S & (S - 1):
            low = S & -S
            A = (S - 1) & S
            while A:
                if A & low:
                    ra, rb = dp[A], dp[S ^ A]
                    for v in range(N):
                        val = ra[v] + rb[v] - w_of[v]
                        if val < row[v]:
                            row[v] = val
                            brow[v] = ("merge", A)
                A = (A - 1) & S
        heap = [(row[v], v) for v in range(N) if row[v] < INF]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > row[v]:
                continue
            for u, w, r in adj[v]:
                nd = d + w + w_of[u]
                if nd < row[u]:
                    row[u] = nd
                    brow[u] = ("edge", v, r)
                    heapq.heappush(heap, (nd, u))
    chosen = set()
    todo = [(full, idx[root])]
    while todo:
        S, v = todo.pop()
        b = back[S][v]
        if b[0] == "edge":
            chosen.add(b[2])
            todo.append((S, b[1]))
        elif b[0] == "merge":
            todo.append((b[1], v))
            todo.append((S ^ b[1], v))
    return dp[full][idx[root]], chosen


def solve(proj, forbid=frozenset()):
    """(cost, sorted chosen link ids) of the tie-rule optimum, or None."""
    n, charge, cold, links = proj["n"], proj["charge"], proj["cold"], proj["links"]
    m = len(links)
    unit = 1 << m
    adj = [[] for _ in range(n + 1)]
    ends = []
    for r, (_lid, lo, hi, cost) in enumerate(links):
        w = cost * unit + (1 << (m - 1 - r))
        ends.append((lo, hi, w))
        if r in forbid or lo == hi:
            continue
        adj[lo].append((hi, w, r))
        adj[hi].append((lo, w, r))
    blocks, disc = _blocks(n, adj)
    if any(disc[c] == -1 for c in cold):
        return None
    terminal = set(cold)
    hang = [False] * (n + 1)
    total = charge[0] * unit
    chosen = set()
    for top, blk in blocks:
        verts = sorted({x for r in blk for x in ends[r][:2]})
        need = [v for v in verts if v != top and (v in terminal or hang[v])]
        if not need:
            continue
        hang[top] = True
        wt = {v: (0 if v == top else charge[v] * unit) for v in verts}
        elist = [(ends[r][0], ends[r][1], ends[r][2], r) for r in blk]
        score, got = _dw(verts, elist, top, need, wt)
        total += score
        chosen |= got
    cost = total >> m
    return cost, sorted(links[r][0] for r in chosen)


def unique(proj, found=None):
    """True when no other link set reaches the optimum cost."""
    found = found or solve(proj)
    rank = {lid: r for r, (lid, *_rest) in enumerate(proj["links"])}
    for lid in found[1]:
        other = solve(proj, frozenset([rank[lid]]))
        if other is not None and other[0] == found[0]:
            return False
    return True
