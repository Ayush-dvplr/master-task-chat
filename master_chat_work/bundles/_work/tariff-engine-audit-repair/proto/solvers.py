"""Kill-test solvers for the redeemed figure (scratch).

usage: python3 -B solvers.py <solver> <corpus.json>  -> JSON {account: [ids]}
Every solver gets (balance_cents, [(id, cents), ...]) and returns ids ascending.
Tie rule (where a solver tracks ids): first id list in plain string order.
"""
import itertools
import json
import sys
from bisect import bisect_right
from math import gcd


# ---------------------------------------------------------------- reference
def reference(balance, vouchers):
    if balance <= 0 or not vouchers:
        return []
    items = sorted(vouchers, key=lambda v: (v[1], v[0]))
    n = len(items)
    suffix_gcd = [0] * (n + 1)
    for index in range(n - 1, -1, -1):
        suffix_gcd[index] = gcd(suffix_gcd[index + 1], items[index][1])
    best = None
    low = 0
    for k in range(0, min(n, 20) + 1):
        unit = suffix_gcd[k]
        if k == n or low < unit:
            cost = (balance // unit if unit else 0) + (1 << k)
            if best is None or cost < best[0]:
                best = (cost, k, unit)
        if k < n:
            low += items[k][1]
    _, k, unit = best
    small, large = items[:k], items[k:]
    chosen = []
    rest = balance
    if large:
        cap = balance // unit
        large.sort()
        mask = (1 << (cap + 1)) - 1
        reach = [1] * (len(large) + 1)
        for index in range(len(large) - 1, -1, -1):
            below = reach[index + 1]
            reach[index] = (below | (below << (large[index][1] // unit))) & mask
        target = reach[0].bit_length() - 1
        rest = balance - target * unit
        for index, (name, amount) in enumerate(large):
            if target == 0:
                break
            step = amount // unit
            if step <= target and (reach[index + 1] >> (target - step)) & 1:
                chosen.append(name)
                target -= step
    small.sort()
    options = [(0, ())]
    for name, amount in small:
        options += [(total + amount, names + (name,)) for total, names in options
                    if total + amount <= rest]
    top = max(total for total, _ in options)
    pick = min(names for total, names in options if total == top)
    return sorted(chosen + list(pick))


# ---------------------------------------------------------------- round 3 blind program (verbatim logic)
def blind_r3(balance, vouchers):
    items = sorted(vouchers)
    mask = (1 << (balance + 1)) - 1
    reach = [1] * (len(items) + 1)
    for index in range(len(items) - 1, -1, -1):
        below = reach[index + 1]
        reach[index] = (below | (below << items[index][1])) & mask
    target = reach[0].bit_length() - 1
    chosen = []
    index = 0
    while target > 0:
        while True:
            voucher, amount = items[index]
            rest = target - amount
            if rest >= 0 and (reach[index + 1] >> rest) & 1:
                chosen.append(voucher)
                target = rest
                index += 1
                break
            index += 1
    return chosen


# ---------------------------------------------------------------- forward bitset over cents, gcd reduced
def bitset(balance, vouchers):
    items = sorted(vouchers)
    unit = 0
    for _, amount in items:
        unit = gcd(unit, amount)
    cap = balance // unit
    mask = (1 << (cap + 1)) - 1
    reach = 1
    for _, amount in items:
        reach = (reach | (reach << (amount // unit))) & mask
    target = reach.bit_length() - 1
    # rebuild with prefix sets is impossible at this width; recompute suffix lazily
    suffix = [1] * (len(items) + 1)
    for index in range(len(items) - 1, -1, -1):
        below = suffix[index + 1]
        suffix[index] = (below | (below << (items[index][1] // unit))) & mask
    chosen = []
    for index, (name, amount) in enumerate(items):
        step = amount // unit
        if target and step <= target and (suffix[index + 1] >> (target - step)) & 1:
            chosen.append(name)
            target -= step
    return chosen


# ---------------------------------------------------------------- forward bitset, optimum sum only (lower bound on any bitset cost)
def bitset_sum_only(balance, vouchers):
    unit = 0
    for _, amount in vouchers:
        unit = gcd(unit, amount)
    mask = (1 << (balance // unit + 1)) - 1
    reach = 1
    for _, amount in vouchers:
        reach = (reach | (reach << (amount // unit))) & mask
    target = (reach.bit_length() - 1) * unit
    return greedy(target, vouchers)


# ---------------------------------------------------------------- dict table sum -> first id tuple
def table(balance, vouchers):
    items = sorted(vouchers)
    best = {0: ()}
    for name, amount in items:
        grown = {}
        for total, names in best.items():
            new = total + amount
            if new <= balance:
                cand = names + (name,)
                old = best.get(new)
                if old is None or cand < old:
                    seen = grown.get(new)
                    if seen is None or cand < seen:
                        grown[new] = cand
        best.update(grown)
    return list(best[max(best)])


# ---------------------------------------------------------------- sorted list merge (Pareto list), prune by bound
def pareto(balance, vouchers):
    items = sorted(vouchers, key=lambda v: -v[1])
    remaining = sum(a for _, a in items)
    states = {0: ()}
    lower = 0
    for name, amount in items:
        remaining -= amount
        grown = dict(states)
        for total, names in states.items():
            new = total + amount
            if new <= balance:
                cand = tuple(sorted(names + (name,)))
                old = grown.get(new)
                if old is None or cand < old:
                    grown[new] = cand
                if new > lower:
                    lower = new
        states = {t: n for t, n in grown.items() if t + remaining >= lower}
    return list(states[max(states)])


# ---------------------------------------------------------------- meet in the middle, raw halves
def _half_raw(part, balance):
    out = [(0, ())]
    for name, amount in part:
        out += [(t + amount, n + (name,)) for t, n in out if t + amount <= balance]
    return out


def _combine(left, right, balance):
    right.sort()
    keys = [t for t, _ in right]
    top = -1
    picks = []
    for total, names in left:
        place = bisect_right(keys, balance - total) - 1
        if place < 0:
            continue
        value = total + keys[place]
        if value > top:
            top, picks = value, []
        if value == top:
            j = place
            while j >= 0 and keys[j] == keys[place]:
                picks.append(tuple(sorted(names + right[j][1])))
                j -= 1
    return list(min(picks))


def mitm(balance, vouchers):
    items = sorted(vouchers)
    half = len(items) // 2
    return _combine(_half_raw(items[:half], balance), _half_raw(items[half:], balance), balance)


# ---------------------------------------------------------------- meet in the middle, halves deduplicated by sum
def _half_dedupe(part, balance):
    best = {0: ()}
    for name, amount in part:
        for total, names in list(best.items()):
            new = total + amount
            if new <= balance:
                cand = tuple(sorted(names + (name,)))
                old = best.get(new)
                if old is None or cand < old:
                    best[new] = cand
    return list(best.items())


def mitm_dedupe(balance, vouchers):
    items = sorted(vouchers)
    half = len(items) // 2
    return _combine(_half_dedupe(items[:half], balance), _half_dedupe(items[half:], balance), balance)


def mitm_dedupe_sorted(balance, vouchers):
    items = sorted(vouchers, key=lambda v: (-v[1], v[0]))
    half = len(items) // 2
    return _combine(_half_dedupe(items[:half], balance), _half_dedupe(items[half:], balance), balance)


# ---------------------------------------------------------------- branch and bound, fractional (sum) bound
def branch_bound(balance, vouchers):
    items = sorted(vouchers, key=lambda v: (-v[1], v[0]))
    n = len(items)
    rest = [0] * (n + 1)
    for index in range(n - 1, -1, -1):
        rest[index] = rest[index + 1] + items[index][1]
    best = [0, ()]
    sys.setrecursionlimit(10000)

    def walk(index, total, names):
        if total > best[0] or (total == best[0] and tuple(sorted(names)) < best[1]):
            best[0], best[1] = total, tuple(sorted(names))
        if index == n or best[0] == balance:
            return
        if total + rest[index] < best[0]:
            return
        name, amount = items[index]
        if total + amount <= balance:
            walk(index + 1, total + amount, names + (name,))
        walk(index + 1, total, names)

    walk(0, 0, ())
    return list(best[1])


# ---------------------------------------------------------------- largest first greedy
def greedy(balance, vouchers):
    chosen, total = [], 0
    for name, amount in sorted(vouchers, key=lambda v: (-v[1], v[0])):
        if total + amount <= balance:
            chosen.append(name)
            total += amount
    return sorted(chosen)


# ---------------------------------------------------------------- naive combinations
def naive(balance, vouchers):
    items = sorted(vouchers)
    best = (0, ())
    for size in range(1, len(items) + 1):
        for combo in itertools.combinations(items, size):
            total = sum(a for _, a in combo)
            if total <= balance and (total > best[0] or (total == best[0] and
                                                         tuple(n for n, _ in combo) < best[1])):
                best = (total, tuple(n for n, _ in combo))
    return list(best[1])


SOLVERS = {name: obj for name, obj in dict(globals()).items()
           if callable(obj) and not name.startswith("_") and name not in (
               "gcd", "bisect_right", "json", "sys", "itertools")}

if __name__ == "__main__":
    solver = SOLVERS[sys.argv[1]]
    data = json.loads(open(sys.argv[2]).read())
    out = {}
    for account in data["accounts"]:
        vouchers = [tuple(v) for v in account["vouchers"]]
        out[account["account"]] = sorted(solver(account["balance"], vouchers))
        print(json.dumps({account["account"]: out[account["account"]]}), flush=True)
