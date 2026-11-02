"""Phase 0b abstract instance generator (extends gen.py).

mode shipped|hidden. Hidden adds: empty base + empty public segment (empty_axes=True),
no_slot fixture behind a season-end closure, both on their own RNG stream (G8).
Returns the abstract instance used by ref.solve plus 'meta' for rendering.
"""
import random

from ref import solve

BASES = ["North", "South", "West", "East"]
TYPES = {"A": {"c": 1, "h": 2, "p": (2, 4)}, "C": {"c": 2, "h": 3, "p": (6, 10)}, "D": {"c": 3, "h": 4, "p": (12, 18)}}
CLASSES = {"widebody": {"rev": 90, "w": 6, "pen": 400}, "narrowbody": {"rev": 50, "w": 4, "pen": 260},
           "regional": {"rev": 20, "w": 2, "pen": 30}}


def make(mode, seed, n, empty_axes=False):
    rng = random.Random(seed)
    rare = random.Random(seed * 7919 + 17)
    hidden = mode == "hidden"
    eb = rare.choice(BASES) if empty_axes else None
    live = [b for b in BASES if b != eb]
    tight = rng.choice(live) if hidden else None
    noslot_base = rare.choice([b for b in live if b != tight]) if hidden else rng.choice(BASES)
    S = 160 if empty_axes else (rng.randint(120, 130) if hidden else 120)
    cls_names = ["widebody", "narrowbody"] if empty_axes else list(CLASSES)
    cls_w = [2, 3] if empty_axes else [2, 3, 3]
    inst = {"S": S, "bases": BASES, "shift_cost": 15,
            "classes": {k: dict(v) for k, v in CLASSES.items()},
            "types": {k: {"c": v["c"], "h": v["h"]} for k, v in TYPES.items()},
            "closed": {b: [] for b in BASES}, "nostart": {}, "checks": []}
    ids = rng.sample(range(10000, 99999), 4 * n + 4)
    k = 0
    twin = None
    for b in BASES:
        t = 1 + rng.randint(0, 3)
        nost = sorted(rng.sample(range(1, S + 1), S // 10))
        inst["nostart"][b] = nost
        if b == eb:
            continue
        for i in range(n):
            ty = rng.choices("ACD", weights=[3, 4, 2])[0]
            p = rng.randint(*TYPES[ty]["p"])
            cl = rng.choices(cls_names, weights=cls_w)[0]
            ps = t
            while ps in nost:
                ps += 1
            due = ps + p - 1 + rng.randint(0, 4)
            r = ps
            if hidden and rng.random() < 0.45:
                r = max(1, ps - rng.randint(1, 6))
            if hidden and i == 1:
                if twin is None:
                    twin = (ty, p, cl, due - ps, ps - r)
                else:
                    ty, p, cl = twin[0], twin[1], twin[2]
                    due, r = ps + twin[3], max(1, ps - twin[4])
            inst["checks"].append({"id": "Q%05d" % ids[k], "base": b, "cls": cl, "type": ty, "p": p,
                                   "ps": ps, "due": due, "r": r})
            k += 1
            t = ps + p + (0 if b == tight else rng.randint(0, 2))
        if b == tight:
            ps = t
            while ps in nost:
                ps += 1
            gcl = "narrowbody" if empty_axes else "regional"
            p = rng.randint(12, 14) if gcl == "regional" else rng.randint(7, 9)
            gty = "D" if gcl == "regional" else "C"
            c = inst["classes"][gcl]
            L = c["pen"] // c["w"] + rng.randint(5, 9)
            L = min(L, S - ps - p)
            inst["checks"].append({"id": "Q%05d" % ids[k], "base": b, "cls": gcl, "type": gty, "p": p,
                                   "ps": ps, "due": ps + p - 1, "r": ps})
            k += 1
            inst["closed"][b] = list(range(ps + 1, ps + 1 + L))
        elif rng.random() < 0.8:
            c0 = rng.randint(10, max(11, min(S - 10, t - 10)))
            ln = rng.randint(3, 9)
            inst["closed"][b] = list(range(c0, c0 + ln))
    # no_slot fixture
    p = rare.randint(12, 18)
    mind = p - 3
    if hidden:
        L2 = rare.randint(15, 25)
        cstart = S - L2 + 1
        r = cstart - rare.randint(3, mind - 1)
        inst["closed"][noslot_base] = sorted(set(inst["closed"][noslot_base]) | set(range(cstart, S + 1)))
    else:
        r = S - mind + 1 + rare.randint(1, 4)
    while r in inst["nostart"][noslot_base]:
        r -= 1
    ncl = "widebody" if empty_axes else rare.choice(list(CLASSES))
    inst["checks"].append({"id": "Q%05d" % ids[k], "base": noslot_base, "cls": ncl, "type": "D", "p": p,
                           "ps": r, "due": r + p - 1, "r": r})
    inst["meta"] = {"mode": mode, "seed": seed, "empty_base": eb, "empty_segment": "public" if empty_axes else None,
                    "tight": tight, "noslot_base": noslot_base, "noslot_id": "Q%05d" % ids[k]}
    inst["K"] = 10 ** 6
    free = solve(inst)["used"]
    inst["K"] = int(0.5 * free) if hidden else free
    inst["meta"]["free_used"] = free
    return inst
