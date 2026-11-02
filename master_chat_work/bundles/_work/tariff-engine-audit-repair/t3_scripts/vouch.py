"""Round-3 voucher solvers: reference (bitset), greedy, naive subsets, dict DP, array DP."""
import itertools


def ref(target, vouchers):
    """vouchers: list of (id, cents). Returns sorted id list."""
    items = sorted((v for v in vouchers if 0 < v[1] <= target), key=lambda v: v[0])
    if target <= 0 or not items:
        return []
    mask = (1 << (target + 1)) - 1
    reach = 1
    for _, a in items:
        reach |= (reach << a) & mask
    best = reach.bit_length() - 1
    if best == 0:
        return []
    n = len(items)
    counts = [1]  # counts[j] = sums reachable with exactly j items
    for _, a in items:
        counts.append(0)
        for j in range(len(counts) - 1, 0, -1):
            counts[j] |= (counts[j - 1] << a) & mask
    kstar = next(j for j in range(len(counts)) if (counts[j] >> best) & 1)
    suffix = [None] * (n + 1)
    suffix[n] = [1] + [0] * kstar
    for i in range(n - 1, -1, -1):
        a = items[i][1]
        prev = suffix[i + 1]
        cur = prev[:]
        for j in range(1, kstar + 1):
            cur[j] |= (prev[j - 1] << a) & mask
        suffix[i] = cur
    chosen, s, k = [], best, kstar
    for i in range(n):
        if k == 0:
            break
        a = items[i][1]
        if a <= s and (suffix[i + 1][k - 1] >> (s - a)) & 1:
            chosen.append(items[i][0])
            s -= a
            k -= 1
    return chosen


def greedy(target, vouchers):
    out, left = [], target
    for vid, a in sorted(vouchers, key=lambda v: (-v[1], v[0])):
        if a <= left:
            out.append(vid)
            left -= a
    return sorted(out)


def naive(target, vouchers):
    items = sorted(vouchers)
    best = (0, 0, ())
    for r in range(1, len(items) + 1):
        for combo in itertools.combinations(items, r):
            s = sum(a for _, a in combo)
            if s <= target:
                ids = tuple(v for v, _ in combo)
                if s > best[0] or (s == best[0] and ids < best[2]):
                    best = (s, 0, ids)
    return list(best[2])


def dictdp(target, vouchers):
    """sum -> lexicographically first id tuple, items in id order."""
    best = {0: ()}
    for vid, a in sorted(vouchers):
        for s, ids in list(best.items()):
            ns = s + a
            if ns > target:
                continue
            cand = ids + (vid,)
            old = best.get(ns)
            if old is None or cand < old:
                best[ns] = cand
    return list(best[max(best)])


def arraydp(target, vouchers):
    """suffix reachability arrays (bytearray) then include-if-completable in id order."""
    items = sorted(vouchers)
    n = len(items)
    if target <= 0:
        return []
    suffix = [None] * (n + 1)
    cur = bytearray(target + 1)
    cur[0] = 1
    suffix[n] = cur
    for i in range(n - 1, -1, -1):
        a = items[i][1]
        nxt = bytearray(cur)
        for s in range(target, a - 1, -1):
            if cur[s - a]:
                nxt[s] = 1
        cur = nxt
        suffix[i] = cur
    best = max(s for s in range(target + 1) if cur[s])
    out, s = [], best
    for i in range(n):
        a = items[i][1]
        if a <= s and suffix[i + 1][s - a]:
            out.append(items[i][0])
            s -= a
    return out


def dfs(target, vouchers):
    """try sums from target down; first include-first search hitting the sum exactly."""
    items = sorted(vouchers)
    n = len(items)
    rest = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        rest[i] = rest[i + 1] + items[i][1]
    def go(i, need, acc):
        if need == 0:
            return acc
        if i == n or rest[i] < need:
            return None
        a = items[i][1]
        if a <= need:
            r = go(i + 1, need - a, acc + [items[i][0]])
            if r is not None:
                return r
        return go(i + 1, need, acc)
    for s in range(min(target, rest[0]), 0, -1):
        r = go(0, s, [])
        if r is not None:
            return r
    return []


def setdp(target, vouchers):
    """Reachable sums as a Python set over vouchers in id order, then lex-first rebuild."""
    items = sorted(vouchers)
    layers = [{0}]
    for _, cents in reversed(items):
        last = layers[-1]
        layers.append(last | {s + cents for s in last if s + cents <= target})
    layers.reverse()
    left = max(layers[0]); out = []
    for k, (v, c) in enumerate(items):
        if c <= left and (left - c) in layers[k + 1]:
            out.append(v); left -= c
    return out
