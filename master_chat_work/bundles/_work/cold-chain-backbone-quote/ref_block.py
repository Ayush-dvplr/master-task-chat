# ---------------------------------------------------------------- reference optimum
#
# The reference network is rebuilt from the contract alone. A block is a set of
# links that stay joined after any one site is taken away: two links meeting at a
# site share a block when their far ends still reach each other without that site.
# Each block that holds a cold room, or a site through which a cold room hangs, is
# solved on its own from its site nearest the depot, either link by link while the
# open connections of the sites still in play are tracked, or by growing partial
# trees from a single queue ordered by price. Links are priced at cost * 2**m plus
# or minus one bit (2**(m-1-r) for the link of rank r in id order): with plus the
# cheapest score is the network the tie rule picks, with minus it is the cheapest
# network whose 0/1 vector is largest, and the cheapest network is the only one
# exactly when the two agree.


def _blocks(n: int, links) -> tuple[list, dict]:
    """[(site nearest the depot, link ranks, sites)] for the live links reached from the depot, and the hop counts."""
    near = [[] for _ in range(n + 1)]
    for r, (_lid, lo, hi, _cost) in enumerate(links):
        if lo != hi:
            near[lo].append((hi, r))
            near[hi].append((lo, r))
    hops = {0: 0}
    queue = [0]
    for v in queue:
        for u, _r in near[v]:
            if u not in hops:
                hops[u] = hops[v] + 1
                queue.append(u)
    owner = {r: r for v in hops for _u, r in near[v]}

    def leader(r):
        while owner[r] != r:
            owner[r] = owner[owner[r]]
            r = owner[r]
        return r

    for v in hops:
        side: dict = {}
        for start, _r in near[v]:
            if start in side:
                continue
            side[start] = start
            queue = [start]
            for x in queue:
                for y, _r2 in near[x]:
                    if y != v and y not in side:
                        side[y] = start
                        queue.append(y)
        first: dict = {}
        for u, r in near[v]:
            if side[u] in first:
                owner[leader(r)] = leader(first[side[u]])
            else:
                first[side[u]] = r
    groups: dict = {}
    for r in owner:
        groups.setdefault(leader(r), []).append(r)
    out = []
    for ranks in groups.values():
        sites = {p for r in ranks for p in links[r][1:3]}
        out.append((min(sites, key=lambda p: (hops[p], p)), sorted(ranks), sites))
    return out, hops


def _link_by_link(root, sites, elist, need, wt):
    """Cheapest tree of one block through root and need; links taken or left one at a time."""
    place = {root: -1, **{p: i for i, p in enumerate(sorted(sites - {root}))}}
    elist = sorted(elist, key=lambda e: (max(place[e[0]], place[e[1]]), min(place[e[0]], place[e[1]]), e[3]))
    final = {}
    for i, (a, b, _w, _r) in enumerate(elist):
        final[a] = final[b] = i
    need = set(need)
    layer = {((root, 1),): (0, None, False)}
    history = []
    for i, (a, b, w, _r) in enumerate(elist):
        nxt: dict = {}
        for key, (score, _prev, _took) in layer.items():
            marks = dict(key)
            marks.setdefault(a, 0)
            marks.setdefault(b, 0)
            options = [(marks, score, False)]
            if not (marks[a] and marks[a] == marks[b]):
                joined = dict(marks)
                spent = score + w
                label = max(joined.values()) + 1
                for x in (a, b):
                    if joined[x] == 0:
                        joined[x] = label
                        label += 1
                        spent += wt[x]
                keep, gone = sorted((joined[a], joined[b]))
                options.append(({s: keep if k == gone else k for s, k in joined.items()}, spent, True))
            for state, spent, took in options:
                state = dict(state)
                alive = True
                for x in (a, b):
                    if final[x] == i and x != root:
                        k = state.pop(x)
                        if (k == 0 and x in need) or (k > 1 and k not in state.values()):
                            alive = False
                if not alive:
                    continue
                names = {0: 0, 1: 1}
                code = tuple((s, names.setdefault(k, len(names))) for s, k in sorted(state.items()))
                held = nxt.get(code)
                if held is None or spent < held[0]:
                    nxt[code] = (spent, key, took)
        history.append(nxt)
        layer = nxt
    key = ((root, 1),)
    best = layer[key][0]
    chosen = set()
    for i in range(len(elist) - 1, -1, -1):
        _s, key_before, took = history[i][key]
        if took:
            chosen.add(elist[i][3])
        key = key_before
    return best, chosen


def _one_queue(root, sites, elist, need, wt):
    """Cheapest tree of one block through root and need; partial trees grown from one price-ordered queue."""
    near = {p: [] for p in sites}
    for a, b, w, r in elist:
        near[a].append((b, w, r))
        near[b].append((a, w, r))
    bit = {t: 1 << i for i, t in enumerate(need)}
    full = (1 << len(need)) - 1
    offer = {(t, bit[t]): (wt[t], None) for t in need}
    queue = [(wt[t], t, bit[t]) for t in need]
    heapq.heapify(queue)
    fixed: dict = {p: {} for p in sites}
    while queue:
        score, v, mask = heapq.heappop(queue)
        if mask in fixed[v] or offer[(v, mask)][0] != score:
            continue
        fixed[v][mask] = score
        if v == root and mask == full:
            break
        for u, w, r in near[v]:
            price = score + w + wt[u]
            if mask not in fixed[u] and price < offer.get((u, mask), (price + 1,))[0]:
                offer[(u, mask)] = (price, ("link", v, r))
                heapq.heappush(queue, (price, u, mask))
        for other, held in list(fixed[v].items()):
            if other & mask:
                continue
            union = other | mask
            price = score + held - wt[v]
            if union not in fixed[v] and price < offer.get((v, union), (price + 1,))[0]:
                offer[(v, union)] = (price, ("join", mask, other))
                heapq.heappush(queue, (price, v, union))
    chosen = set()
    todo = [(root, full)]
    while todo:
        v, mask = todo.pop()
        how = offer[(v, mask)][1]
        if how is None:
            continue
        if how[0] == "link":
            chosen.add(how[2])
            todo.append((how[1], mask))
        else:
            todo.append((v, how[1]))
            todo.append((v, how[2]))
    return fixed[root][full], chosen


def _optimum(proj: dict):
    """(cost, 1 when the cheapest link set is the only one else 2, tie-rule link set) or None."""
    n, charge, cold, links = proj["n"], proj["charge"], proj["cold"], proj["links"]
    m = len(links)
    unit = 1 << m
    blocks, hops = _blocks(n, links)
    if any(c not in hops for c in cold):
        return None
    total = charge[0]
    picks: dict = {1: set(), -1: set()}
    hanging: set = set()
    for root, ranks, sites in sorted(blocks, key=lambda b: (-hops[b[0]], b[1])):
        need = sorted(p for p in sites if p != root and (p in cold or p in hanging))
        if not need:
            continue
        hanging.add(root)
        wt = {p: (0 if p == root else charge[p] * unit) for p in sites}
        narrow = len(need) > 11
        for sign in (1, -1):
            elist = [(links[r][1], links[r][2], links[r][3] * unit + sign * (1 << (m - 1 - r)), r) for r in ranks]
            if narrow:
                score, got = _link_by_link(root, sites, elist, need, wt)
            else:
                score, got = _one_queue(root, sites, elist, need, wt)
            picks[sign] |= got
            if sign == 1:
                total += score >> m
    return total, 1 if picks[1] == picks[-1] else 2, sorted(links[r][0] for r in picks[1])
