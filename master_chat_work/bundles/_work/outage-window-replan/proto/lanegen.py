"""Lane generator for the kill test (prototype). tier: shipped (quiet) or hidden (contended)."""
import random

from lane import Lane, DEFER_FACTOR


def factor_calendar(rng, H):
    f = [0] * (H + 2)
    d = 1
    while d <= H:
        L = rng.randint(3, 8)
        v = rng.choice([1, 2, 2, 3])
        for x in range(d, min(H, d + L - 1) + 1):
            f[x] = v
        d += L
    return f


def gen_lane(seed, tier, n=None, H=91):
    if tier == "tiny":
        H = 18
    rng = random.Random(seed * 7919 + (1 if tier == "hidden" else 0))
    f = factor_calendar(rng, H)
    base = rng.choice([1, 2])
    cap = [base] * (H + 2)
    blackout = set(rng.sample(range(1, H + 1), 6))
    if n is None:
        n = rng.randint(6, 10) if tier == "shipped" else rng.randint(14, 22)
    reqs = []
    if tier == "tiny":
        n = rng.randint(3, 5)
        cap = [rng.choice([1, 1, 2]) if x % 7 else 0 for x in range(H + 2)]
        for k in range(n):
            dur = rng.randint(1, 3)
            e = rng.randint(1, 8)
            win = rng.randint(dur, dur + 5)
            reqs.append(dict(crews=rng.choice([1, 1, 2]), dur=dur, e=e, l=min(H, e + win - 1), w=rng.randint(1, 5)))
    elif tier == "shipped":
        for k in range(n):
            dur = rng.randint(1, 4)
            e = rng.randint(1, H - 20)
            win = rng.randint(dur + 2, dur + 12)
            reqs.append(dict(crews=1, dur=dur, e=e, l=min(H, e + win - 1), w=rng.randint(1, 12)))
    else:
        # contention clusters: crew loss over a cheap stretch, several requests competing
        ncl = rng.randint(2, 4)
        per = n // ncl
        starts = sorted(rng.sample(range(5, H - 25, 3), ncl))
        for c in range(ncl):
            a = starts[c]
            Ls = rng.randint(5, 9)
            for x in range(a, a + Ls):
                f[x] = 1
            for x in list(range(a - 4, a)) + list(range(a + Ls, a + Ls + 4)):
                if 1 <= x <= H:
                    f[x] = 3
            for x in range(a - 4, a + Ls + 4):
                if 1 <= x <= H:
                    cap[x] = 1
            for k in range(per):
                dur = rng.randint(2, 4)
                e = max(1, a - rng.randint(0, 4))
                l = min(H, a + Ls - 1 + rng.randint(0, 6))
                reqs.append(dict(crews=1, dur=dur, e=e, l=l, w=rng.randint(2, 12)))
        # exact tie pairs: flat cheap stretch of length d1+d2 at crew 1, flanked by factor 3,
        # windows equal the stretch, the lower id is the lighter request
        tie_rng = random.Random(seed * 104729 + 17)
        for tp in range(tie_rng.randint(1, 2)):
            d1, d2 = tie_rng.randint(1, 3), tie_rng.randint(1, 3)
            a = tie_rng.randint(8, H - 12)
            Ls = d1 + d2
            for x in range(a, a + Ls):
                f[x] = 1
                cap[x] = 1
            for x in (a - 1, a - 2, a + Ls, a + Ls + 1):
                if 1 <= x <= H:
                    f[x] = 3
            wl = tie_rng.randint(2, 5)
            wh = wl + tie_rng.randint(2, 6)
            reqs.append(dict(crews=1, dur=d1, e=a, l=a + Ls - 1, w=wl, tie=(tp, 0)))
            reqs.append(dict(crews=1, dur=d2, e=a, l=a + Ls - 1, w=wh, tie=(tp, 1)))
        # keep pairs: published X inside a flat stretch of 5 days at crew 1, not at the earliest start;
        # a heavier new Y with the same window; only the fewest-moved level keeps X in place
        keep_rng = random.Random(seed * 15485863 + 3)
        planted = []
        for kp in range(keep_rng.randint(1, 2)):
            a = keep_rng.randint(8, H - 12)
            for x in range(a, a + 5):
                f[x] = 1
                cap[x] = 1
                planted.append(x)
            for x in (a - 1, a - 2, a + 5, a + 6):
                if 1 <= x <= H:
                    f[x] = 3
            wx = keep_rng.randint(2, 5)
            wy = wx + keep_rng.randint(1, 6)
            reqs.append(dict(crews=1, dur=2, e=a, l=a + 4, w=wx, keep=(kp, 0), pubset=a + 1))
            reqs.append(dict(crews=1, dur=2, e=a, l=a + 4, w=wy, keep=(kp, 1), new=True))
        while len(reqs) < n:
            dur = rng.randint(1, 4)
            e = rng.randint(1, H - 20)
            win = rng.randint(dur + 2, dur + 12)
            reqs.append(dict(crews=rng.choice([1, 1, base]), dur=dur, e=e, l=min(H, e + win - 1), w=rng.randint(1, 12)))
    rng.shuffle(reqs)
    pos = {}
    for k, r in enumerate(reqs):
        if "tie" in r:
            pos.setdefault(r["tie"][0], {})[r["tie"][1]] = k
        if "keep" in r:
            pos.setdefault(("k", r["keep"][0]), {})[r["keep"][1]] = k
    for tp, pr in pos.items():
        if pr[0] > pr[1]:
            reqs[pr[0]], reqs[pr[1]] = reqs[pr[1]], reqs[pr[0]]
    for k, r in enumerate(reqs):
        r["id"] = "A%03d" % k
        r["pub"] = None
    # published plan: a plausible earlier plan (random feasible-ish start in window, or None for new)
    for r in reqs:
        if rng.random() < 0.7:
            r["pub"] = rng.randint(r["e"], max(r["e"], r["l"] - r["dur"] + 1))
        if "tie" in r or r.get("new"):
            r["pub"] = None
        if "pubset" in r:
            r["pub"] = r["pubset"]
    inc = []
    prec = []
    m = len(reqs)
    for _ in range(rng.randint(0, 2)):
        i, j = rng.sample(range(m), 2)
        inc.append((min(i, j), max(i, j)))
    for _ in range(rng.randint(0, 1)):
        i, j = rng.sample(range(m), 2)
        prec.append((i, j))
    if tier == "hidden":
        blackout = {x for x in blackout if x not in set(planted) and all(not (r.get("tie") or r.get("keep")) or not (r["e"] <= x <= r["l"]) for r in reqs)}
    d = dict(H=H, cap=cap, factor=f, blackout=sorted(blackout), reqs=reqs, incompat=inc, prec=prec)
    return d
