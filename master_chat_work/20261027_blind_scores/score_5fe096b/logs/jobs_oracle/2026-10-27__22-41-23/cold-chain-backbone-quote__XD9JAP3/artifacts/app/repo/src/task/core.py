"""Minimum quote of a project.

The open links fall into groups that meet one another only at single sites.
Each group hangs below the site it shares with the part nearer the depot, so
the groups are solved one at a time, deepest first: inside a group the sites
to join are its cold rooms and every site with a needed group below it.  A
group with few such sites is solved over subsets of them; any other group is
swept in corridor order, keeping the joined classes of the sites that still
have a link ahead.  Every link weighs cost * 2**m plus a bit of its rank in
link-id order, so the smallest weight is also the smaller link vector.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from .parser import Project


@dataclass(frozen=True)
class Network:
    quote: int
    links: tuple[str, ...]
    sites: tuple[str, ...]


def _groups(n, adj):
    """Link groups reachable from the depot, deepest first: [(top site, [link index])]."""
    disc = [-1] * (n + 1)
    low = [0] * (n + 1)
    disc[0] = 0
    clock = 1
    edges, out = [], []
    stack = [(0, -1, iter(adj[0]))]
    while stack:
        v, came, nbrs = stack[-1]
        moved = False
        for u, _w, r in nbrs:
            if r == came:
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
                group = []
                while True:
                    r = edges.pop()
                    group.append(r)
                    if r == came:
                        break
                out.append((p, group))
    return out, disc


def _by_subsets(verts, elist, root, need, wt):
    """Cheapest tree joining root and need inside one group: (weight, link indexes)."""
    idx = {v: i for i, v in enumerate(verts)}
    size = len(verts)
    adj = [[] for _ in range(size)]
    for a, b, w, r in elist:
        adj[idx[a]].append((idx[b], w, r))
        adj[idx[b]].append((idx[a], w, r))
    own = [wt[v] for v in verts]
    full = (1 << len(need)) - 1
    best = [[None] * size for _ in range(full + 1)]
    back = [[None] * size for _ in range(full + 1)]
    for i, t in enumerate(need):
        best[1 << i][idx[t]] = own[idx[t]]
        back[1 << i][idx[t]] = ("leaf",)
    for whole in range(1, full + 1):
        row, brow = best[whole], back[whole]
        if whole & (whole - 1):
            low = whole & -whole
            part = (whole - 1) & whole
            while part:
                if part & low:
                    ra, rb = best[part], best[whole ^ part]
                    for v in range(size):
                        if ra[v] is not None and rb[v] is not None:
                            val = ra[v] + rb[v] - own[v]
                            if row[v] is None or val < row[v]:
                                row[v] = val
                                brow[v] = ("merge", part)
                part = (part - 1) & whole
        heap = [(row[v], v) for v in range(size) if row[v] is not None]
        heapq.heapify(heap)
        while heap:
            d, v = heapq.heappop(heap)
            if d > row[v]:
                continue
            for u, w, r in adj[v]:
                nd = d + w + own[u]
                if row[u] is None or nd < row[u]:
                    row[u] = nd
                    brow[u] = ("link", v, r)
                    heapq.heappush(heap, (nd, u))
    chosen = set()
    todo = [(full, idx[root])]
    while todo:
        whole, v = todo.pop()
        step = back[whole][v]
        if step[0] == "link":
            chosen.add(step[2])
            todo.append((whole, step[1]))
        elif step[0] == "merge":
            todo.append((step[1], v))
            todo.append((whole ^ step[1], v))
    return best[full][idx[root]], chosen


def _order(verts, elist, root):
    order = [root] + sorted(v for v in verts if v != root)
    step = {v: i for i, v in enumerate(order)}
    last = dict(step)
    for a, b, _w, _r in elist:
        hi = max(step[a], step[b])
        last[a] = max(last[a], hi)
        last[b] = max(last[b], hi)
    return order, step, last


def _along(verts, elist, root, need, wt):
    """Same answer as _by_subsets, by a sweep in corridor order."""
    order, step, last = _order(verts, elist, root)
    nbr = {v: [] for v in order}
    for a, b, w, r in elist:
        nbr[a].append((b, w, r))
        nbr[b].append((a, w, r))
    need = set(need)
    layers = [{((root, 0),): (wt[root], None, ())}]
    for i, v in enumerate(order[1:], 1):
        arriving = [(u, w, r) for u, w, r in nbr[v] if step[u] < i]
        layer = {}
        for key, (weight, _back, _took) in layers[-1].items():
            tags = dict(key)
            options = [] if v in need else [(dict(tags), weight, ())]
            grown = [({**tags, v: max(tags.values()) + 1}, weight + wt[v], ())]
            for u, w, r in arriving:
                if u not in tags:
                    continue
                extra = []
                for cur, spent, took in grown:
                    a, b = cur[u], cur[v]
                    if a == b:
                        continue
                    keep, drop = min(a, b), max(a, b)
                    joined = {s: (keep if t == drop else t) for s, t in cur.items()}
                    extra.append((joined, spent + w, took + (r,)))
                grown += extra
            options += grown
            for cur, spent, took in options:
                lost = False
                for s in [s for s in cur if last[s] <= i and s != root]:
                    tag = cur.pop(s)
                    if tag != 0 and tag not in cur.values():
                        lost = True
                        break
                if lost:
                    continue
                names = {0: 0}
                nxt = []
                for s, t in sorted(cur.items()):
                    names.setdefault(t, len(names))
                    nxt.append((s, names[t]))
                nxt = tuple(nxt)
                held = layer.get(nxt)
                if held is None or spent < held[0]:
                    layer[nxt] = (spent, key, took)
        layers.append(layer)
    weight, key = min((e[0], k) for k, e in layers[-1].items() if all(t == 0 for _s, t in k))
    chosen = set()
    for i in range(len(order) - 1, 0, -1):
        _w, back, took = layers[i][key]
        chosen.update(took)
        key = back
    return weight, chosen


def _bell(k):
    row = [1]
    for _ in range(k):
        nxt = [row[-1]]
        for x in row:
            nxt.append(nxt[-1] + x)
        row = nxt
    return row[0]


def _subsets_cheaper(verts, elist, root, k):
    """Compare the state counts of the two methods for one group."""
    order, step, last = _order(verts, elist, root)
    alive = max(sum(1 for v in order if step[v] < i <= last[v]) for i in range(len(order)))
    return 3 ** k <= _bell(alive + 1) << alive


def _solve(project: Project, banned=frozenset()):
    """(quote, sorted link ids) of the tie-rule optimum, or None."""
    n, charge, cold = project.size, project.charges, project.cold
    links = project.links
    m = len(links)
    unit = 1 << m
    adj = [[] for _ in range(n + 1)]
    ends = []
    for r, (lid, pa, pb, cost) in enumerate(links):
        w = cost * unit + (1 << (m - 1 - r))
        ends.append((pa, pb, w))
        if lid in banned or pa == pb:
            continue
        adj[pa].append((pb, w, r))
        adj[pb].append((pa, w, r))
    groups, disc = _groups(n, adj)
    if any(disc[c] == -1 for c in cold):
        return None
    below = [False] * (n + 1)
    total = charge[0] * unit
    chosen = set()
    for top, group in groups:
        verts = sorted({x for r in group for x in ends[r][:2]})
        need = [v for v in verts if v != top and (v in cold or below[v])]
        if not need:
            continue
        below[top] = True
        wt = {v: (0 if v == top else charge[v] * unit) for v in verts}
        elist = [(ends[r][0], ends[r][1], ends[r][2], r) for r in group]
        if _subsets_cheaper(verts, elist, top, len(need)):
            weight, got = _by_subsets(verts, elist, top, need, wt)
        else:
            weight, got = _along(verts, elist, top, need, wt)
        total += weight
        chosen |= got
    return total >> m, tuple(sorted(links[r][0] for r in chosen))


def best_network(project: Project) -> Network:
    """Minimum-quote network; among equal quotes the smaller link vector wins."""
    quote, links = _solve(project)
    return Network(quote, links, tuple(sorted(activated(project, links))))


def unique(project: Project) -> bool:
    """True when no other link set reaches the minimum quote."""
    quote, links = _solve(project)
    for lid in links:
        other = _solve(project, frozenset([lid]))
        if other is not None and other[0] == quote:
            return False
    return True


def activated(project: Project, links) -> set[str]:
    chosen = set(links)
    active = {0} | project.cold
    for lid, pa, pb, _cost in project.links:
        if lid in chosen:
            active.update((pa, pb))
    return {project.ids[p] for p in active}


def site_lines(project: Project, links) -> dict[int, int]:
    """Total per activated position: its activation charge once, plus its booked links."""
    chosen = set(links)
    lines = {0: project.charges[0]}
    for p in project.cold:
        lines[p] = project.charges[p]
    for lid, pa, pb, cost in project.links:
        if lid in chosen:
            for p in (pa, pb):
                lines.setdefault(p, project.charges[p])
            lines[pb] += cost
    return lines


def quote_of(project: Project, links) -> int:
    return sum(site_lines(project, links).values())
