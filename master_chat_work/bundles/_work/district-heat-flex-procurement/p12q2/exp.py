"""Offline experiments on dumped calls: python3 -B exp.py VARIANT ROOT [ROOT...]"""
import bisect
import pickle
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def exact(call, order_mode="id", strong=True):
    cands, goals, caps, floors_here = call["cands"], call["goals"], call["caps"], call["floors"]
    cw, vw, width, segment_names = call["cw"], call["vw"], call["width"], call["segs"]
    nseg = len(segment_names)
    segix = {g: i for i, g in enumerate(segment_names)}
    floor_ticks = [floors_here[g][0] for g in segment_names]
    floor_pen = [floors_here[g][1] for g in segment_names]
    per_site = {}
    for sid, oid, cost, r, v, seg in cands:
        per_site.setdefault(sid, []).append((oid, cw * cost, r, v, segix[seg]))
    order = sorted(per_site)
    if order_mode == "relief":
        order.sort(key=lambda s: -max(sum(o[2]) for o in per_site[s]))
    n = len(order)
    more = [[0] * width for _ in range(n + 1)]
    more_seg = [[0] * nseg for _ in range(n + 1)]
    for k in range(n - 1, -1, -1):
        opts = per_site[order[k]]
        more[k] = [more[k + 1][t] + max(o[2][t] for o in opts) for t in range(width)]
        more_seg[k] = list(more_seg[k + 1])
        more_seg[k][opts[0][4]] += max(sum(o[2]) for o in opts)
    # per layer and interval: later sites as relaxed items (largest relief, lowest price among offers giving any)
    cover = []
    for k in range(n + 1):
        row = []
        for t in range(width):
            items = []
            for s in order[k:]:
                good = [o for o in per_site[s] if o[2][t] > 0]
                if good:
                    items.append((max(o[2][t] for o in good), min(o[1] + vw * sum(o[3]) for o in good)))
            by_ratio = sorted(items, key=lambda it: it[1] / it[0])
            amt, price, acc_a, acc_p = [], [], 0, 0
            for a, p in by_ratio:
                acc_a += a
                acc_p += p
                amt.append(acc_a)
                price.append(acc_p)
            big = sorted((a for a, _ in items), reverse=True)
            cnt, acc = [], 0
            for a in big:
                acc += a
                cnt.append(acc)
            row.append((by_ratio, amt, price, cnt))
        cover.append(row)

    def extra(k, need):
        """lowest price and fewest offers that can still add need[t] relief in each interval"""
        lo_price = lo_count = 0
        for t in range(width):
            d = need[t]
            if d <= 0:
                continue
            by_ratio, amt, price, cnt = cover[k][t]
            j = bisect.bisect_left(amt, d)
            if j < len(amt):
                before_a = amt[j - 1] if j else 0
                before_p = price[j - 1] if j else 0
                a, p = by_ratio[j]
                # fractional last item, rounded down so the bound stays a bound
                lo_price = max(lo_price, before_p + (p * (d - before_a)) // a)
            c = bisect.bisect_left(cnt, d)
            lo_count = max(lo_count, c + 1)
        return lo_price, lo_count

    def key_at(rel, rec, segs, spent, used, k, best1):
        gaps = [goals[t][0] - rel[t] for t in range(width)]
        gap = sum(goals[t][1] * max(0, gaps[t] - more[k][t]) for t in range(width))
        deficit = sum(floor_pen[j] * max(0, floor_ticks[j] - segs[j] - more_seg[k][j]) for j in range(nseg))
        third = spent + vw * sum(rec)
        excess = sum(max(0, -g) for g in gaps)
        if strong and k < n and best1 is not None and gap == best1:
            p, c = extra(k, [min(gaps[t], more[k][t]) if goals[t][1] > 0 else 0 for t in range(width)])
            return (gap, deficit, third + p, excess, used + c)
        return (gap, deficit, third, excess, used)

    def fits(rel, rec):
        return all(rel[t] <= caps[t][0] and rec[t] <= caps[t][1] for t in range(width))

    def total(pick):
        rel, rec, segs = [0] * width, [0] * width, [0] * nseg
        spent = used = 0
        for ch in pick:
            if ch is None:
                continue
            _, cost, r, v, j = ch
            for t in range(width):
                rel[t] += r[t]
                rec[t] += v[t]
            segs[j] += sum(r)
            spent += cost
            used += 1
        return key_at(rel, rec, segs, spent, used, n, None) if fits(rel, rec) else None

    pick = [None] * n
    best = total(pick)
    moved = True
    while moved:
        moved = False
        for k in range(n):
            for ch in [None] + per_site[order[k]]:
                if ch is pick[k]:
                    continue
                trial = pick[:k] + [ch] + pick[k + 1:]
                got = total(trial)
                if got is not None and got < best:
                    best, pick, moved = got, trial, True
    zero = (0,) * width
    table = {(zero, zero, (0,) * nseg): (0, 0, 1, ())}
    peak = 1
    for k, sid in enumerate(order):
        nxt = {}
        for (rel, rec, segs), item in table.items():
            states = [((rel, rec, segs), item)]
            spent, used, ways, ids = item
            for oid, cost, r, v, j in per_site[sid]:
                nrel = tuple(rel[t] + r[t] for t in range(width))
                nrec = tuple(rec[t] + v[t] for t in range(width))
                if not fits(nrel, nrec):
                    continue
                ns = list(segs)
                ns[j] = min(floor_ticks[j], ns[j] + sum(r))
                states.append(((nrel, nrec, tuple(ns)), (spent + cost, used + 1, ways, tuple(sorted(ids + (oid,))))))
            for state, it in states:
                old = nxt.get(state)
                if old is None or it[:2] < old[:2]:
                    nxt[state] = it
                elif it[:2] == old[:2]:
                    nxt[state] = (old[0], old[1], old[2] + it[2], max(old[3], it[3]))
        for (rel, rec, segs), it in nxt.items():
            done = key_at(rel, rec, segs, it[0], it[1], n, None)
            if done < best:
                best = done
        table = {s: it for s, it in nxt.items() if key_at(*s, it[0], it[1], k + 1, best[0]) <= best}
        peak = max(peak, len(table))
    ways, ids = 0, ()
    for (rel, rec, segs), (spent, used, w, got) in table.items():
        if key_at(rel, rec, segs, spent, used, n, None) == best:
            ways += w
            ids = max(ids, got)
    return (ids, ways), peak


def main():
    variant = sys.argv[1]
    mode, strong = variant.split("-")
    for root in sys.argv[2:]:
        calls = pickle.loads((HERE / f"calls_{root}.pkl").read_bytes())
        t0 = time.perf_counter()
        bad = 0
        worst = (0, None)
        for c in calls:
            t1 = time.perf_counter()
            got, peak = exact(c, mode, strong == "strong")
            dt = time.perf_counter() - t1
            if got != tuple(c["want"]) and got != c["want"]:
                bad += 1
                if bad <= 3:
                    print("  MISMATCH", c["eid"], c["region"], got, c["want"], flush=True)
            if dt > worst[0]:
                worst = (dt, f"{c['eid']} {c['region']} n={len(c['cands'])} peak={peak}")
        print(f"{variant} {root}: calls {len(calls)} mismatches {bad} total {time.perf_counter() - t0:.1f}s "
              f"worst {worst[0]:.1f}s {worst[1]}", flush=True)


if __name__ == "__main__":
    signal.alarm(1500)
    main()
