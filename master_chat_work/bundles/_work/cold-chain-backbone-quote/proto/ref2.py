"""Bundle reference prototype: split at cut sites; inside a block use
Dreyfus-Wagner when few sites are needed, else an exact sweep over the
block's corridor order. Scores are cost*2^m + link bit, so the integer
minimum is the tie-rule optimum."""
from __future__ import annotations

from ref import _blocks, _dw

FORCE = None  # tests only: True = always DW, False = always sweep


def _sweep(verts, elist, root, need, wt):
    order = [root] + sorted(v for v in verts if v != root)
    step = {v: i for i, v in enumerate(order)}
    nbr = {v: [] for v in order}
    for a, b, w, r in elist:
        nbr[a].append((b, w, r))
        nbr[b].append((a, w, r))
    last = {v: max([step[v]] + [step[u] for u, _w, _r in nbr[v]]) for v in order}
    need = set(need)
    layers = [{((root, 0),): (wt[root], None, ())}]
    for i, v in enumerate(order[1:], 1):
        arriving = [(u, w, r) for u, w, r in nbr[v] if step[u] < i]
        layer = {}
        for key, (cost, _b, _t) in layers[-1].items():
            tags = dict(key)
            branches = [] if v in need else [(dict(tags), cost, ())]
            fresh = max(tags.values()) + 1
            grown = [({**tags, v: fresh}, cost + wt[v], ())]
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
            branches += grown
            for cur, spent, took in branches:
                dead = False
                for s in [s for s in cur if last[s] <= i and s != root]:
                    tag = cur.pop(s)
                    if tag != 0 and tag not in cur.values():
                        dead = True
                        break
                if dead:
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
    ends = [(e[0], k) for k, e in layers[-1].items() if all(t == 0 for _s, t in k)]
    best, key = min(ends)
    chosen = set()
    for i in range(len(order) - 1, 0, -1):
        _c, back, took = layers[i][key]
        chosen.update(took)
        key = back
    return best, chosen


def _bell(k):
    row = [1]
    for _ in range(k):
        nxt = [row[-1]]
        for x in row:
            nxt.append(nxt[-1] + x)
        row = nxt
    return row[0]


def _prefer_dw(verts, elist, root, k):
    """Cheaper of the two methods by a state-count estimate."""
    if FORCE is not None:
        return FORCE
    order = [root] + sorted(v for v in verts if v != root)
    step = {v: i for i, v in enumerate(order)}
    last = dict(step)
    for a, b, _w, _r in elist:
        hi = max(step[a], step[b])
        last[a] = max(last[a], hi)
        last[b] = max(last[b], hi)
    width = max(sum(1 for v in order if step[v] < i <= last[v]) for i in range(len(order)))
    return 3 ** k <= _bell(width + 1) << width


def solve(proj, forbid=frozenset()):
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
        if _prefer_dw(verts, elist, top, len(need)):
            score, got = _dw(verts, elist, top, need, wt)
        else:
            score, got = _sweep(verts, elist, top, need, wt)
        total += score
        chosen |= got
    return total >> m, sorted(links[r][0] for r in chosen)


def unique(proj, found=None):
    found = found or solve(proj)
    rank = {lid: r for r, (lid, *_rest) in enumerate(proj["links"])}
    for lid in found[1]:
        other = solve(proj, frozenset([rank[lid]]))
        if other is not None and other[0] == found[0]:
            return False
    return True
