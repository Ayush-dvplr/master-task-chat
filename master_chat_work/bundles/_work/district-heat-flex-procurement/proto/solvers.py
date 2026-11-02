"""Generic solvers for the portfolio problem (scratch). Each returns (key, ways, ids)."""
from __future__ import annotations

import itertools


def unpack(p):
    n = p["n"]
    tv = [t[0] for t in p["target"]]
    tw = [t[1] for t in p["target"]]
    lr = [l[0] for l in p["limit"]]
    lv = [l[1] for l in p["limit"]]
    segs = sorted(p["floors"])
    return n, tv, tw, lr, lv, segs


def key_of(p, taken):
    n, tv, tw, lr, lv, segs = unpack(p)
    rel = [sum(o["rel"][t] for o in taken) for t in range(n)]
    rec = [sum(o["rec"][t] for o in taken) for t in range(n)]
    if any(rel[t] > lr[t] or rec[t] > lv[t] for t in range(n)):
        return None
    got = {s: 0 for s in segs}
    for o in taken:
        got[o["seg"]] += sum(o["rel"])
    short = sum(tw[t] * max(0, tv[t] - rel[t]) for t in range(n))
    deficit = sum(w * max(0, fl - got[s]) for s, (fl, w) in p["floors"].items())
    blended = p["cw"] * sum(o["cost"] for o in taken) + p["rw"] * sum(rec)
    over = sum(max(0, rel[t] - tv[t]) for t in range(n))
    return (short, deficit, blended, over, len(taken))


def dfs_plain(p):
    """solve.py: every choice visited, cut only on ceilings."""
    n, tv, tw, lr, lv, segs = unpack(p)
    lanes = p["lanes"]
    best = [None, 0, ()]
    taken = []

    def visit(i):
        if i == len(lanes):
            k = key_of(p, taken)
            ids = tuple(sorted(o["id"] for o in taken))
            if best[0] is None or k < best[0]:
                best[:] = [k, 1, ids]
            elif k == best[0]:
                best[1] += 1
                best[2] = max(best[2], ids)
            return
        visit(i + 1)
        for o in lanes[i]:
            taken.append(o)
            if key_of(p, taken) is not None:
                visit(i + 1)
            taken.pop()

    visit(0)
    return tuple(best)


def naive(p):
    """itertools.product over every lane, no cut at all."""
    best = [None, 0, ()]
    for combo in itertools.product(*[[None] + lane for lane in p["lanes"]]):
        taken = [o for o in combo if o is not None]
        k = key_of(p, taken)
        if k is None:
            continue
        ids = tuple(sorted(o["id"] for o in taken))
        if best[0] is None or k < best[0]:
            best[:] = [k, 1, ids]
        elif k == best[0]:
            best[1] += 1
            best[2] = max(best[2], ids)
    return tuple(best)


def bnb(p):
    """Opus probe-9 shape: DFS, optimistic shortfall and floor bounds from suffix maxima, strict cut, ties visited."""
    n, tv, tw, lr, lv, segs = unpack(p)
    lanes = p["lanes"]
    L = len(lanes)
    sufmax = [[0] * n for _ in range(L + 1)]
    sufseg = [{s: 0 for s in segs} for _ in range(L + 1)]
    for i in range(L - 1, -1, -1):
        for t in range(n):
            sufmax[i][t] = sufmax[i + 1][t] + max([0] + [o["rel"][t] for o in lanes[i]])
        for s in segs:
            sufseg[i][s] = sufseg[i + 1][s] + max([0] + [sum(o["rel"]) for o in lanes[i] if o["seg"] == s])
    rel = [0] * n
    rec = [0] * n
    got = {s: 0 for s in segs}
    taken = []
    best = [None, 0, ()]
    cw, rw = p["cw"], p["rw"]

    def lb(i):
        short = sum(tw[t] * max(0, tv[t] - min(lr[t], rel[t] + sufmax[i][t])) for t in range(n))
        deficit = sum(w * max(0, fl - got[s] - sufseg[i][s]) for s, (fl, w) in p["floors"].items())
        blended = cw * sum(o["cost"] for o in taken) + rw * sum(rec)
        over = sum(max(0, rel[t] - tv[t]) for t in range(n))
        return (short, deficit, blended, over, len(taken))

    def visit(i):
        if best[0] is not None and lb(i) > best[0]:
            return
        if i == L:
            k = key_of(p, taken)
            ids = tuple(sorted(o["id"] for o in taken))
            if best[0] is None or k < best[0]:
                best[:] = [k, 1, ids]
            elif k == best[0]:
                best[1] += 1
                best[2] = max(best[2], ids)
            return
        visit(i + 1)
        for o in lanes[i]:
            if any(rel[t] + o["rel"][t] > lr[t] or rec[t] + o["rec"][t] > lv[t] for t in range(n)):
                continue
            for t in range(n):
                rel[t] += o["rel"][t]
                rec[t] += o["rec"][t]
            got[o["seg"]] += sum(o["rel"])
            taken.append(o)
            visit(i + 1)
            taken.pop()
            got[o["seg"]] -= sum(o["rel"])
            for t in range(n):
                rel[t] -= o["rel"][t]
                rec[t] -= o["rec"][t]

    visit(0)
    return tuple(best)


def dp(p, stats=None):
    """Exact DP over sites in id order; state = (relief vector, recovery vector, segment relief)."""
    n, tv, tw, lr, lv, segs = unpack(p)
    cw = p["cw"]
    si = {s: j for j, s in enumerate(segs)}
    states = {(tuple([0] * n), tuple([0] * n), tuple([0] * len(segs))): (0, 0, 1, ())}
    peak = 1
    for lane in p["lanes"]:
        nxt = dict(states)
        for (r, v, g), (c, k, w, ids) in states.items():
            for o in lane:
                r2 = tuple(a + b for a, b in zip(r, o["rel"]))
                v2 = tuple(a + b for a, b in zip(v, o["rec"]))
                if any(r2[t] > lr[t] or v2[t] > lv[t] for t in range(n)):
                    continue
                g2 = list(g)
                g2[si[o["seg"]]] += sum(o["rel"])
                st = (r2, v2, tuple(g2))
                val = (c + cw * o["cost"], k + 1, w, ids + (o["id"],))
                cur = nxt.get(st)
                if cur is None or val[:2] < cur[:2]:
                    nxt[st] = val
                elif val[:2] == cur[:2]:
                    nxt[st] = (cur[0], cur[1], cur[2] + w, max(cur[3], val[3]))
        states = nxt
        peak = max(peak, len(states))
    best = [None, 0, ()]
    for (r, v, g), (c, k, w, ids) in states.items():
        short = sum(tw[t] * max(0, tv[t] - r[t]) for t in range(n))
        deficit = sum(wt * max(0, fl - g[si[s]]) for s, (fl, wt) in p["floors"].items())
        key = (short, deficit, c + p["rw"] * sum(v), sum(max(0, r[t] - tv[t]) for t in range(n)), k)
        if best[0] is None or key < best[0]:
            best[:] = [key, w, ids]
        elif key == best[0]:
            best[1] += w
            best[2] = max(best[2], ids)
    if stats is not None:
        stats["peak"] = peak
    return tuple(best)


def greedy(p):
    """Cheapest relief first: offers by blended cost per relief tick, kept when the key improves."""
    n, tv, tw, lr, lv, segs = unpack(p)
    offers = [o for lane in p["lanes"] for o in lane]
    offers.sort(key=lambda o: ((p["cw"] * o["cost"] + p["rw"] * sum(o["rec"])) / max(1, sum(o["rel"])), o["id"]))
    taken, used = [], set()
    cur = key_of(p, [])
    for o in offers:
        site = o["id"].rsplit("-", 1)[0]
        if site in used:
            continue
        k = key_of(p, taken + [o])
        if k is not None and k < cur:
            taken.append(o)
            used.add(site)
            cur = k
    return (cur, 1, tuple(sorted(o["id"] for o in taken)))


def merit(p):
    """Merit order: offers by bid cost ascending, stacked while shortfall drops."""
    n, tv, tw, lr, lv, segs = unpack(p)
    offers = sorted((o for lane in p["lanes"] for o in lane), key=lambda o: (o["cost"], o["id"]))
    taken, used = [], set()
    cur = key_of(p, [])
    for o in offers:
        site = o["id"].rsplit("-", 1)[0]
        if site in used:
            continue
        k = key_of(p, taken + [o])
        if k is not None and k[:2] < cur[:2]:
            taken.append(o)
            used.add(site)
            cur = k
    return (cur, 1, tuple(sorted(o["id"] for o in taken)))


SOLVERS = {"dfs_plain": dfs_plain, "naive": naive, "bnb": bnb, "dp": dp, "greedy": greedy, "merit": merit}


NODES = [0]


def grouped(p):
    """Copy of p whose lanes hold one representative per class of identical offers (greatest id), with mult."""
    q = dict(p)
    lanes = []
    for lane in p["lanes"]:
        cls = {}
        for o in lane:
            k = (tuple(o["rel"]), tuple(o["rec"]), o["cost"])
            cls.setdefault(k, []).append(o)
        lanes.append([dict(max(g, key=lambda o: o["id"]), mult=len(g)) for g in cls.values()])
    q["lanes"] = lanes
    return q


def ref(p):
    """bnb shape, identical offers at one site collapsed into one branch whose ways multiply."""
    q = grouped(p)
    n, tv, tw, lr, lv, segs = unpack(q)
    lanes = q["lanes"]
    L = len(lanes)
    sufmax = [[0] * n for _ in range(L + 1)]
    sufseg = [{s: 0 for s in segs} for _ in range(L + 1)]
    for i in range(L - 1, -1, -1):
        for t in range(n):
            sufmax[i][t] = sufmax[i + 1][t] + max([0] + [o["rel"][t] for o in lanes[i]])
        for s in segs:
            sufseg[i][s] = sufseg[i + 1][s] + max([0] + [sum(o["rel"]) for o in lanes[i] if o["seg"] == s])
    rel = [0] * n
    rec = [0] * n
    got = {s: 0 for s in segs}
    taken = []
    best = [None, 0, ()]
    cw, rw = q["cw"], q["rw"]

    def lb(i):
        short = sum(tw[t] * max(0, tv[t] - min(lr[t], rel[t] + sufmax[i][t])) for t in range(n))
        deficit = sum(w * max(0, fl - got[s] - sufseg[i][s]) for s, (fl, w) in q["floors"].items())
        blended = cw * sum(o["cost"] for o in taken) + rw * sum(rec)
        over = sum(max(0, rel[t] - tv[t]) for t in range(n))
        return (short, deficit, blended, over, len(taken))

    def visit(i, ways):
        NODES[0] += 1
        if best[0] is not None and lb(i) > best[0]:
            return
        if i == L:
            k = key_of(q, taken)
            ids = tuple(sorted(o["id"] for o in taken))
            if best[0] is None or k < best[0]:
                best[:] = [k, ways, ids]
            elif k == best[0]:
                best[1] += ways
                best[2] = max(best[2], ids)
            return
        visit(i + 1, ways)
        for o in lanes[i]:
            if any(rel[t] + o["rel"][t] > lr[t] or rec[t] + o["rec"][t] > lv[t] for t in range(n)):
                continue
            for t in range(n):
                rel[t] += o["rel"][t]
                rec[t] += o["rec"][t]
            got[o["seg"]] += sum(o["rel"])
            taken.append(o)
            visit(i + 1, ways * o["mult"])
            taken.pop()
            got[o["seg"]] -= sum(o["rel"])
            for t in range(n):
                rel[t] -= o["rel"][t]
                rec[t] -= o["rec"][t]

    visit(0, 1)
    return tuple(best)


SOLVERS["ref"] = ref


def ref2(p, group=True):
    """bnb shape, identical offers at one site collapsed into one branch whose ways multiply."""
    q = grouped(p) if group else dict(p, lanes=[[dict(o, mult=1) for o in lane] for lane in p["lanes"]])
    n, tv, tw, lr, lv, segs = unpack(q)
    lanes = sorted(q["lanes"], key=lambda lane: -max(sum(o["rel"]) for o in lane))
    lanes = [sorted(lane, key=lambda o: -sum(o["rel"])) for lane in lanes]
    L = len(lanes)
    sufmax = [[0] * n for _ in range(L + 1)]
    sufseg = [{s: 0 for s in segs} for _ in range(L + 1)]
    for i in range(L - 1, -1, -1):
        for t in range(n):
            sufmax[i][t] = sufmax[i + 1][t] + max([0] + [o["rel"][t] for o in lanes[i]])
        for s in segs:
            sufseg[i][s] = sufseg[i + 1][s] + max([0] + [sum(o["rel"]) for o in lanes[i] if o["seg"] == s])
    rel = [0] * n
    rec = [0] * n
    got = {s: 0 for s in segs}
    taken = []
    best = [None, 0, ()]
    cw, rw = q["cw"], q["rw"]

    def lb(i):
        short = sum(tw[t] * max(0, tv[t] - min(lr[t], rel[t] + sufmax[i][t])) for t in range(n))
        deficit = sum(w * max(0, fl - got[s] - sufseg[i][s]) for s, (fl, w) in q["floors"].items())
        blended = cw * sum(o["cost"] for o in taken) + rw * sum(rec)
        over = sum(max(0, rel[t] - tv[t]) for t in range(n))
        return (short, deficit, blended, over, len(taken))

    def visit(i, ways):
        NODES[0] += 1
        if best[0] is not None and lb(i) > best[0]:
            return
        if i == L:
            k = key_of(q, taken)
            ids = tuple(sorted(o["id"] for o in taken))
            if best[0] is None or k < best[0]:
                best[:] = [k, ways, ids]
            elif k == best[0]:
                best[1] += ways
                best[2] = max(best[2], ids)
            return
        for o in lanes[i]:
            if any(rel[t] + o["rel"][t] > lr[t] or rec[t] + o["rec"][t] > lv[t] for t in range(n)):
                continue
            for t in range(n):
                rel[t] += o["rel"][t]
                rec[t] += o["rec"][t]
            got[o["seg"]] += sum(o["rel"])
            taken.append(o)
            visit(i + 1, ways * o["mult"])
            taken.pop()
            got[o["seg"]] -= sum(o["rel"])
            for t in range(n):
                rel[t] -= o["rel"][t]
                rec[t] -= o["rec"][t]
        visit(i + 1, ways)

    visit(0, 1)
    return tuple(best)


SOLVERS["ref2"] = ref2


SOLVERS["bnb_ord"] = lambda p: ref2(p, group=False)


def ref3(p, order=True):
    """Layered states (relief, recovery, segment relief) merged, cut by an optimistic key against the best completion."""
    n, tv, tw, lr, lv, segs = unpack(p)
    cw, rw = p["cw"], p["rw"]
    si = {s: j for j, s in enumerate(segs)}
    fl = [(si[s], f, w) for s, (f, w) in p["floors"].items()]
    lanes = [lane for lane in p["lanes"] if lane]
    if order:
        lanes.sort(key=lambda lane: -max(sum(o["rel"]) for o in lane))
    L = len(lanes)
    sufmax = [[0] * n for _ in range(L + 1)]
    sufseg = [[0] * len(segs) for _ in range(L + 1)]
    for i in range(L - 1, -1, -1):
        for t in range(n):
            sufmax[i][t] = sufmax[i + 1][t] + max([0] + [o["rel"][t] for o in lanes[i]])
        for s in segs:
            sufseg[i][si[s]] = sufseg[i + 1][si[s]] + max([0] + [sum(o["rel"]) for o in lanes[i] if o["seg"] == s])
    prepped = [[(tuple(o["rel"]), tuple(o["rec"]), si[o["seg"]], sum(o["rel"]), cw * o["cost"], o["id"]) for o in lane]
               for lane in lanes]

    def done_key(r, v, g, c, k):
        return (sum(tw[t] * max(0, tv[t] - r[t]) for t in range(n)),
                sum(w * max(0, f - g[j]) for j, f, w in fl), c + rw * sum(v),
                sum(max(0, r[t] - tv[t]) for t in range(n)), k)

    def low_key(i, r, v, g, c, k):
        sm, sg = sufmax[i], sufseg[i]
        return (sum(tw[t] * max(0, tv[t] - min(lr[t], r[t] + sm[t])) for t in range(n)),
                sum(w * max(0, f - g[j] - sg[j]) for j, f, w in fl), c + rw * sum(v),
                sum(max(0, r[t] - tv[t]) for t in range(n)), k)

    z = tuple([0] * n)
    states = {(z, z, tuple([0] * len(segs))): (0, 0, 1, ())}
    inc = done_key(z, z, tuple([0] * len(segs)), 0, 0)
    for i, lane in enumerate(prepped):
        nxt = dict(states)
        for (r, v, g), (c, k, w, ids) in states.items():
            for orl, orc, oj, osum, oc, oid in lane:
                r2 = tuple(a + b for a, b in zip(r, orl))
                if any(r2[t] > lr[t] for t in range(n)):
                    continue
                v2 = tuple(a + b for a, b in zip(v, orc))
                if any(v2[t] > lv[t] for t in range(n)):
                    continue
                g2 = list(g)
                g2[oj] += osum
                st = (r2, v2, tuple(g2))
                c2, k2 = c + oc, k + 1
                cur = nxt.get(st)
                if cur is None or (c2, k2) < cur[:2]:
                    nxt[st] = (c2, k2, w, tuple(sorted(ids + (oid,))))
                elif (c2, k2) == cur[:2]:
                    nxt[st] = (c2, k2, cur[2] + w, max(cur[3], tuple(sorted(ids + (oid,)))))
        for (r, v, g), (c, k, w, ids) in nxt.items():
            dk = done_key(r, v, g, c, k)
            if dk < inc:
                inc = dk
        states = {st: val for st, val in nxt.items() if low_key(i + 1, st[0], st[1], st[2], val[0], val[1]) <= inc}
    best = [None, 0, ()]
    for (r, v, g), (c, k, w, ids) in states.items():
        key = done_key(r, v, g, c, k)
        if best[0] is None or key < best[0]:
            best[:] = [key, w, ids]
        elif key == best[0]:
            best[1] += w
            best[2] = max(best[2], ids)
    return tuple(best)


SOLVERS["ref3"] = ref3


def blind(p):
    """The 8caff6e blind program's own optimise(), fed the same problem."""
    import importlib.util
    from pathlib import Path
    if "blind_mod" not in globals():
        spec = importlib.util.spec_from_file_location("blind_mod", Path(__file__).resolve().parent / "progs/blind_derive_report.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        globals()["blind_mod"] = mod
    eid, reg = p["er"]
    n = p["n"]
    cands, sites = [], {}
    for lane in p["lanes"]:
        for o in lane:
            sid = o["id"].rsplit("-", 1)[0]
            key = (eid, sid)
            sites[key] = {"segment": o["seg"]}
            cands.append({"key": key, "rel": o["rel"], "rec": o["rec"], "cost": o["cost"], "relsum": sum(o["rel"]),
                          "recsum": sum(o["rec"]), "offer_id": o["id"]})
    targets = {(eid, reg, t + 1): tuple(p["target"][t]) for t in range(n)}
    ceilings = {(eid, reg, t + 1): tuple(p["limit"][t]) for t in range(n)}
    floors = {(eid, reg, s): tuple(v) for s, v in p["floors"].items()}
    res = blind_mod.optimise(eid, reg, n, p["cw"], p["rw"], cands, sites, targets, ceilings, floors, sorted(p["floors"]))
    chosen = res["chosen"]
    return (key_of(p, [o for lane in p["lanes"] for o in lane if o["id"] in {c["offer_id"] for c in chosen}]),
            res["tied"], tuple(sorted(c["offer_id"] for c in chosen)))


SOLVERS["blind"] = blind
