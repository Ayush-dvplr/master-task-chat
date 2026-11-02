"""Prototype MWIS solvers for the flood-repair-portfolio premortem.

Graph: n vertices, integer weights W (tie-break already folded in), adj[i] = bitmask of neighbours.
"""
import random, time, sys

sys.setrecursionlimit(100000)


class Timeout(Exception):
    pass


def bits(m):
    while m:
        b = m & -m
        yield b.bit_length() - 1
        m ^= b


def popcount(m):
    return bin(m).count("1")


def tiebreak_weights(w, rank):
    """Fold the lexicographic-smallest-id-list tie-break into one integer weight."""
    n = len(w)
    return [w[i] * (1 << n) + (1 << (n - 1 - rank[i])) for i in range(n)]


def build_adj(n, cliques, pairs):
    adj = [0] * n
    for c in cliques:
        m = 0
        for v in c:
            m |= 1 << v
        for v in c:
            adj[v] |= m & ~(1 << v)
    for a, b in pairs:
        if a != b:
            adj[a] |= 1 << b
            adj[b] |= 1 << a
    return adj


def is_independent(adj, S):
    for v in bits(S):
        if adj[v] & S:
            return False
    return True


def weight_of(W, S):
    return sum(W[v] for v in bits(S))


# ---------------------------------------------------------------- bounds
def clique_cover_ub(W, adj, mask, order):
    """Greedy weighted clique cover: vertices in decreasing weight, each joins the first clique it fits."""
    cliques = []  # list of [member_mask, max_weight]
    total = 0
    for v in order:
        if not (mask >> v) & 1:
            continue
        av = adj[v]
        for i, c in enumerate(cliques):
            if c & ~av == 0:
                cliques[i] = c | (1 << v)
                break
        else:
            cliques.append(1 << v)
            total += W[v]
    return total


# ---------------------------------------------------------------- generic exact 1: classic B&B
def bnb_classic(n, W, adj, limit, initial=None):
    order = sorted(range(n), key=lambda v: -W[v])
    best = [0, 0]
    if initial is not None:
        best = [weight_of(W, initial), initial]
    deadline = time.time() + limit
    cnt = [0]

    def rec(mask, cur, cs):
        cnt[0] += 1
        if cnt[0] & 1023 == 0 and time.time() > deadline:
            raise Timeout
        # take isolated vertices
        changed = True
        while changed:
            changed = False
            for v in bits(mask):
                if adj[v] & mask == 0:
                    cur += W[v]; cs |= 1 << v; mask &= ~(1 << v); changed = True
        if mask == 0:
            if cur > best[0]:
                best[0], best[1] = cur, cs
            return
        if cur + clique_cover_ub(W, adj, mask, order) <= best[0]:
            return
        v = max(bits(mask), key=lambda u: (popcount(adj[u] & mask), W[u]))
        rec(mask & ~(1 << v) & ~adj[v], cur + W[v], cs | (1 << v))
        rec(mask & ~(1 << v), cur, cs)

    try:
        rec((1 << n) - 1, 0, 0)
        return True, best[0], best[1], cnt[0]
    except Timeout:
        return False, best[0], best[1], cnt[0]


# ---------------------------------------------------------------- generic exact 2: memo + components + reductions + bound
def components(adj, mask):
    out = []
    while mask:
        v = (mask & -mask)
        comp = v
        frontier = v
        while frontier:
            nb = 0
            for u in bits(frontier):
                nb |= adj[u]
            nb &= mask & ~comp
            comp |= nb
            frontier = nb
        out.append(comp)
        mask &= ~comp
    return out


def bnb_memo(n, W, adj, limit, use_bound=True, use_dom=True, memo_cap=2_000_000):
    order = sorted(range(n), key=lambda v: -W[v])
    memo = {}
    deadline = time.time() + limit
    cnt = [0]
    NEG = (-1, 0)

    def f(mask):
        cnt[0] += 1
        if cnt[0] & 1023 == 0 and time.time() > deadline:
            raise Timeout
        if mask == 0:
            return (0, 0)
        r = memo.get(mask)
        if r is not None:
            return r
        orig = mask
        cur, cs = 0, 0
        changed = True
        while changed and mask:
            changed = False
            for v in bits(mask):
                if not (mask >> v) & 1:
                    continue
                nb = adj[v] & mask
                if nb == 0:
                    cur += W[v]; cs |= 1 << v; mask &= ~(1 << v); changed = True
                elif nb & (nb - 1) == 0:
                    u = nb.bit_length() - 1
                    if W[v] >= W[u]:
                        cur += W[v]; cs |= 1 << v; mask &= ~(1 << v) & ~nb; changed = True
            if use_dom and not changed:
                # u adjacent v, N[v] subset of N[u], W[v] >= W[u] -> delete u
                for v in bits(mask):
                    Nv = (adj[v] & mask) | (1 << v)
                    for u in bits(adj[v] & mask):
                        Nu = (adj[u] & mask) | (1 << u)
                        if Nv & ~Nu == 0 and W[v] >= W[u]:
                            mask &= ~(1 << u); changed = True
                            break
                    if changed:
                        break
        if mask == 0:
            res = (cur, cs)
        else:
            comps = components(adj, mask)
            if len(comps) > 1:
                tv, ts = cur, cs
                for c in comps:
                    a, s = f(c)
                    tv += a; ts |= s
                res = (tv, ts)
            else:
                v = max(bits(mask), key=lambda u: (popcount(adj[u] & mask), W[u]))
                a, s = f(mask & ~(1 << v) & ~adj[v])
                take = (a + W[v], s | (1 << v))
                rest = mask & ~(1 << v)
                if (not use_bound) or clique_cover_ub(W, adj, rest, order) > take[0]:
                    skip = f(rest)
                    res0 = take if take[0] >= skip[0] else skip
                else:
                    res0 = take
                res = (res0[0] + cur, res0[1] | cs)
        if len(memo) < memo_cap:
            memo[orig] = res
        return res

    try:
        v, s = f((1 << n) - 1)
        return True, v, s, cnt[0]
    except Timeout:
        return False, None, None, cnt[0]


# ---------------------------------------------------------------- reference: elimination-order DP (tree decomposition)
def elimination_order(n, adj, heuristic="minfill"):
    g = [adj[v] for v in range(n)]
    alive = (1 << n) - 1
    order = []
    for _ in range(n):
        best = None
        for v in bits(alive):
            nb = g[v] & alive
            if heuristic == "mindeg":
                score = popcount(nb)
            else:
                fill = 0
                for u in bits(nb):
                    fill += popcount(nb & ~g[u] & ~(1 << u))
                score = (fill, popcount(nb))
            if best is None or score < best[0]:
                best = (score, v)
        v = best[1]
        nb = g[v] & alive
        for u in bits(nb):
            g[u] |= nb & ~(1 << u)
        alive &= ~(1 << v)
        order.append(v)
    return order


def width_of(n, adj, order):
    g = [adj[v] for v in range(n)]
    alive = (1 << n) - 1
    w = 0
    for v in order:
        nb = g[v] & alive
        w = max(w, popcount(nb))
        for u in bits(nb):
            g[u] |= nb & ~(1 << u)
        alive &= ~(1 << v)
    return w


def indep_subsets(adj, scope_list):
    """All independent subsets (as masks) of the vertex list scope_list."""
    out = [0]
    for v in scope_list:
        bv = 1 << v
        av = adj[v]
        out += [s | bv for s in out if s & av == 0]
    return out


def ref_solve(n, W, adj, order=None):
    if order is None:
        order = elimination_order(n, adj)
    pos = {v: i for i, v in enumerate(order)}
    g = [adj[v] for v in range(n)]
    alive = (1 << n) - 1
    bucket = [[] for _ in range(n)]  # messages: (scope_mask, table dict assignment->(val, chosen))
    final = []
    maxstates = 0
    for v in order:
        nb = g[v] & alive
        for u in bits(nb):
            g[u] |= nb & ~(1 << u)
        alive &= ~(1 << v)
        msgs = bucket[v]
        S = list(bits(nb))
        subs = indep_subsets(adj, S)
        maxstates = max(maxstates, len(subs))
        bv = 1 << v
        table = {}
        av = adj[v]
        for T in subs:
            # v not chosen
            val0, ch0 = 0, 0
            for sc, tb in msgs:
                r = tb[T & sc]
                val0 += r[0]; ch0 |= r[1]
            best = (val0, ch0)
            if T & av == 0:
                X = T | bv
                val1, ch1 = W[v], bv
                ok = True
                for sc, tb in msgs:
                    r = tb.get(X & sc)
                    if r is None:
                        ok = False; break
                    val1 += r[0]; ch1 |= r[1]
                if ok and val1 > best[0]:
                    best = (val1, ch1)
            table[T] = best
        if S:
            target = min(S, key=lambda u: pos[u])
            bucket[target].append((nb, table))
        else:
            final.append(table[0])
    val = sum(t[0] for t in final)
    ch = 0
    for t in final:
        ch |= t[1]
    return val, ch, maxstates


# ---------------------------------------------------------------- baselines
def greedy(n, W, adj, key="w"):
    if key == "w":
        order = sorted(range(n), key=lambda v: -W[v])
    else:
        order = sorted(range(n), key=lambda v: -W[v] / (popcount(adj[v]) + 1))
    S = 0
    for v in order:
        if adj[v] & S == 0:
            S |= 1 << v
    return S


def local_search(n, W, adj, S, two=True):
    improved = True
    while improved:
        improved = False
        # (1, k) moves: add v, drop its selected neighbours
        for v in range(n):
            if (S >> v) & 1:
                continue
            drop = adj[v] & S
            if W[v] > weight_of(W, drop):
                S = (S & ~drop) | (1 << v); improved = True
        if improved or not two:
            continue
        # (2, k) moves: add non-adjacent u, v, drop their selected neighbours
        for v in range(n):
            if (S >> v) & 1:
                continue
            for u in range(v + 1, n):
                if (S >> u) & 1 or (adj[v] >> u) & 1:
                    continue
                drop = (adj[v] | adj[u]) & S
                if W[v] + W[u] > weight_of(W, drop):
                    S = (S & ~drop) | (1 << v) | (1 << u); improved = True
                    break
            if improved:
                break
    return S


def brute(n, W, adj):
    best = (0, 0)
    def rec(i, S, val):
        nonlocal best
        if i == n:
            if val > best[0]:
                best = (val, S)
            return
        if adj[i] & S == 0:
            rec(i + 1, S | (1 << i), val + W[i])
        rec(i + 1, S, val)
    rec(0, 0, 0)
    return best


def ils(n, W, adj, limit, seed=0, start=None):
    """Iterated local search: force-in perturbation + (1,k)/(2,k) improvement; anytime incumbent."""
    rng = random.Random(seed)
    S = start if start is not None else max((greedy(n, W, adj, "w"), greedy(n, W, adj, "ratio")), key=lambda s: weight_of(W, s))
    S = local_search(n, W, adj, S, two=False)
    best, bestv = S, weight_of(W, S)
    curv = bestv
    deadline = time.time() + limit
    it = 0
    while time.time() < deadline:
        it += 1
        T = S
        for _ in range(rng.randint(1, 3)):
            v = rng.randrange(n)
            T = (T & ~adj[v]) | (1 << v)
        T = local_search(n, W, adj, T, two=(it % 8 == 0))
        tv = weight_of(W, T)
        if tv >= curv or rng.random() < 0.02:
            S, curv = T, tv
        if tv > bestv:
            best, bestv = T, tv
    return best


def bfs_order(n, adj):
    """Cuthill-McKee style order from a peripheral vertex (pseudo-diameter end)."""
    def bfs(s):
        seen = 1 << s; order = [s]; i = 0
        while i < len(order):
            v = order[i]; i += 1
            nb = adj[v] & ~seen
            for u in sorted(bits(nb), key=lambda u: popcount(adj[u])):
                order.append(u)
            seen |= nb
        return order
    s = min(range(n), key=lambda v: popcount(adj[v]))
    for _ in range(3):
        s = bfs(s)[-1]
    order = bfs(s)
    left = [v for v in range(n) if v not in set(order)]
    return order + left


def memo_ordered(n, W, adj, limit, order=None):
    """Exact memo recursion branching on the first remaining vertex of a fixed (BFS) order."""
    if order is None:
        order = bfs_order(n, adj)
    memo = {}
    deadline = time.time() + limit
    cnt = [0]

    def f(mask):
        cnt[0] += 1
        if cnt[0] & 1023 == 0 and time.time() > deadline:
            raise Timeout
        if mask == 0:
            return (0, 0)
        r = memo.get(mask)
        if r is not None:
            return r
        for v in order:
            if (mask >> v) & 1:
                break
        a, s = f(mask & ~(1 << v) & ~adj[v])
        take = (a + W[v], s | (1 << v))
        skip = f(mask & ~(1 << v))
        res = take if take[0] >= skip[0] else skip
        memo[mask] = res
        return res

    try:
        v, s = f((1 << n) - 1)
        return True, v, s, cnt[0]
    except Timeout:
        return False, None, None, cnt[0]
