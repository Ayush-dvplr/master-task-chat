"""Brute force check of ref.py on tiny random instances (every start day, every compression)."""
import itertools
import random
import sys

import ref
from gen import CLASSES

TYPES = {"A": {"c": 1, "h": 2, "p": (2, 3)}, "C": {"c": 2, "h": 3, "p": (3, 5)}}


def tiny(seed, layout, S):
    rng = random.Random(seed)
    bases = list(layout)
    inst = {"S": S, "bases": bases, "shift_cost": 15, "classes": CLASSES,
            "types": {k: {"c": v["c"], "h": v["h"]} for k, v in TYPES.items()},
            "closed": {}, "nostart": {}, "checks": [], "K": rng.choice([0, 2, 3, 4, 6, 9])}
    ids = rng.sample(range(100, 999), sum(layout.values()))
    k = 0
    for b, n in layout.items():
        inst["closed"][b] = sorted(rng.sample(range(1, S + 1), rng.randint(0, 3)))
        inst["nostart"][b] = sorted(rng.sample(range(1, S + 1), rng.randint(0, 3)))
        for _ in range(n):
            ty = rng.choice("AC")
            p = rng.randint(*TYPES[ty]["p"])
            ps = rng.randint(1, S - 2)
            r = ps if rng.random() < 0.5 else max(1, ps - rng.randint(1, 4))
            inst["checks"].append({"id": "Q%03d" % ids[k], "base": b, "cls": rng.choice(list(CLASSES)),
                                   "type": ty, "p": p, "ps": ps, "due": ps + p - 1 + rng.randint(-3, 2), "r": r})
            k += 1
    return inst


def options(inst, ch):
    S = inst["S"]
    b = ch["base"]
    closed = set(inst["closed"][b])
    nost = set(inst["nostart"][b])
    ty = inst["types"][ch["type"]]
    out = [None]
    for x in range(0, min(ty["c"], ch["p"] - 1) + 1):
        dur = ch["p"] - x
        for s in range(ch["r"], S + 1):
            if ref.feasible_start(s, dur, closed, nost, S):
                out.append((s, s + dur - 1, x))
    return out


def brute(inst):
    S = inst["S"]
    checks = sorted(inst["checks"], key=lambda c: c["id"])
    opts = [options(inst, c) for c in checks]
    best = None
    for combo in itertools.product(*opts):
        ot = 0
        ok = True
        lines = {}
        for ch, o in zip(checks, combo):
            if o is None:
                continue
            ot += inst["types"][ch["type"]]["h"] * o[2]
            lines.setdefault(ch["base"], []).append(o)
        if ot > inst["K"]:
            continue
        for segs in lines.values():
            segs.sort()
            for a, b in zip(segs, segs[1:]):
                if b[0] <= a[1]:
                    ok = False
        if not ok:
            continue
        t1 = t2 = t3 = 0
        for ch, o in zip(checks, combo):
            c = inst["classes"][ch["cls"]]
            if o is None:
                t1 += c["pen"]
                t3 += 1
                continue
            s, f, x = o
            t1 += c["w"] * max(0, f - ch["due"])
            t2 += c["rev"] * (f - s + 1) + inst["shift_cost"] * inst["types"][ch["type"]]["h"] * x
            t3 += 1 if s != ch["ps"] else 0
        st = tuple(S + 1 if o is None else o[0] for o in combo)
        fi = tuple(S + 1 if o is None else o[1] for o in combo)
        key = (t1, t2, t3, st, fi)
        if best is None or key < best[0]:
            best = (key, combo)
    return best


if __name__ == "__main__":
    n = int(sys.argv[1])
    bad = 0
    for seed in range(n):
        layout = {"North": 2, "South": 2} if seed % 2 else {"North": 4}
        inst = tiny(seed, layout, 16 if seed % 2 else 14)
        b = brute(inst)
        r = ref.solve(inst)
        checks = sorted(inst["checks"], key=lambda c: c["id"])
        rp = tuple(r["plan"][c["id"]][0] for c in checks)
        if tuple(r["T"]) != b[0][:3] or rp != b[0][3]:
            bad += 1
            print("MISMATCH seed", seed, r["T"], b[0][:3], rp, b[0][3])
    print("checked", n, "mismatches", bad)
