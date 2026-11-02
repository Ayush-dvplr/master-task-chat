"""Prototype instance generator (kill test only). gen(seed, tier) -> list of 4 region dicts."""
import random
import core

TYPES = ["line", "substation", "protection"]
H = 91


def factor_calendar(rng):
    f = [3] * (H + 2)
    d = 1
    while d <= H:
        L = rng.randint(3, 8)
        v = rng.choice([1, 2, 2, 3])
        for x in range(d, min(H, d + L - 1) + 1):
            f[x] = v
        d += L
    return f


def base_region(rng, tier):
    cap = {t: [0] + [rng.choice([1, 2, 2])] * H + [0] for t in TYPES}
    # make cap lists independent per day
    cap = {t: [cap[t][1]] * (H + 2) for t in TYPES}
    for t in TYPES:
        cap[t][0] = cap[t][H + 1] = 0
    f = factor_calendar(rng)
    bl = set(rng.sample(range(1, H + 1), 6))
    return cap, f, bl


def mk_req(rng, rid, t, dur, e, l, w, crews=1):
    return {"id": rid, "type": t, "crews": crews, "dur": dur, "e": e, "l": l, "w": w, "pub": None}


def gen_region(rng, tier, rname):
    cap, f, bl = base_region(rng, tier)
    reqs = []
    used_ids = set()

    def nid():
        while True:
            x = "%s-%04d" % (rname[0], rng.randint(1000, 9999))
            if x not in used_ids:
                used_ids.add(x)
                return x

    loss = []  # (type, d0, d1) crew loss of 1 crew
    if tier == "shipped":
        nfill, nclu, ntie = 24, 0, 0
    else:
        nfill, nclu, ntie = rng.randint(30, 45), rng.randint(3, 5), rng.randint(1, 3)
    # filler: wide windows, low density
    for _ in range(nfill):
        t = rng.choice(TYPES)
        dur = rng.randint(1, 4)
        e = rng.randint(1, H - 20)
        l = min(H, e + dur - 1 + rng.randint(6, 20))
        w = rng.randint(1, 9) * rng.choice([1, 3])
        reqs.append(mk_req(rng, nid(), t, dur, e, l, w))
    clusters = []
    for _ in range(nclu):
        t = rng.choice(TYPES)
        L = rng.randint(5, 9)
        a = rng.randint(8, H - L - 8)
        for x in range(a, a + L):
            f[x] = 1
        for x in list(range(a - 4, a)) + list(range(a + L, a + L + 4)):
            f[x] = 3
        for x in range(a - 4, a + L + 4):
            bl.discard(x)
        loss.append((t, a - 4, a + L + 3))
        k = rng.randint(4, 6)
        mem = []
        for _ in range(k):
            dur = rng.randint(2, 4)
            e = a - rng.randint(0, 3)
            l = a + L - 1 + rng.randint(0, 3)
            w = rng.randint(2, 12)
            r = mk_req(rng, nid(), t, dur, e, l, w)
            reqs.append(r)
            mem.append(r)
        clusters.append(mem)
    for _ in range(ntie):
        t = rng.choice(TYPES)
        d1, d2 = rng.randint(1, 3), rng.randint(1, 3)
        a = rng.randint(6, H - d1 - d2 - 6)
        for x in range(a, a + d1 + d2):
            f[x] = 1
            bl.discard(x)
        for x in list(range(a - 3, a)) + list(range(a + d1 + d2, a + d1 + d2 + 3)):
            f[x] = 3
        loss.append((t, a - 3, a + d1 + d2 + 2))
        lo, hi = sorted([nid(), nid()])
        wl, wh = sorted(rng.sample(range(2, 12), 2))
        r1 = mk_req(rng, lo, t, d1, a, a + d1 + d2 - 1, wl)
        r2 = mk_req(rng, hi, t, d2, a, a + d1 + d2 - 1, wh)
        r1["new"] = r2["new"] = True
        reqs += [r1, r2]
    reqs.sort(key=lambda r: r["id"])
    for r in reqs:
        r.setdefault("new", False)
    if tier != "shipped":
        # some cluster members are new urgent requests from the notice
        for mem in clusters:
            for r in mem:
                if rng.random() < 0.3:
                    r["new"] = True
    idx = {r["id"]: i for i, r in enumerate(reqs)}
    inc = []
    prec = []
    n = len(reqs)
    for _ in range(rng.randint(1, 3)):
        i, j = rng.sample(range(n), 2)
        inc.append((min(i, j), max(i, j)))
    for _ in range(rng.randint(0, 2)):
        i, j = rng.sample(range(n), 2)
        a, b = reqs[i], reqs[j]
        if a["e"] + a["dur"] <= b["l"] - b["dur"] + 1:
            prec.append((i, j))
    # published plan = reference on pre-disruption instance (no loss, no new requests)
    keep = [i for i in range(n) if not reqs[i]["new"]]
    kmap = {i: k for k, i in enumerate(keep)}
    pre = {"H": H, "cap": {t: list(cap[t]) for t in TYPES}, "factor": f, "blackout": bl,
           "reqs": [dict(reqs[i]) for i in keep],
           "incompat": [(kmap[i], kmap[j]) for i, j in inc if i in kmap and j in kmap],
           "prec": [(kmap[i], kmap[j]) for i, j in prec if i in kmap and j in kmap]}
    PI = core.Inst(pre)
    pplan = core.reference(PI)
    for k, i in enumerate(keep):
        reqs[i]["pub"] = pplan[k] if pplan[k] != PI.DEF else None
    post_cap = {t: list(cap[t]) for t in TYPES}
    for t, d0, d1 in loss:
        for d in range(max(1, d0), min(H, d1) + 1):
            post_cap[t][d] = 1 if post_cap[t][d] >= 1 else 0
    return {"H": H, "cap": post_cap, "factor": f, "blackout": bl, "reqs": reqs,
            "incompat": inc, "prec": prec, "name": rname}


def gen(seed, tier):
    rng = random.Random(seed)
    return [gen_region(rng, tier, rn) for rn in ["North", "South", "West", "East"]]
