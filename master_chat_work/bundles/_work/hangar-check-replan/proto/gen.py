"""Prototype abstract instance generator. mode shipped|hidden. Usage: gen.py mode seed n_per_base out.json"""
import json
import random
import sys

BASES = ["North", "South", "West", "East"]
TYPES = {"A": {"c": 1, "h": 2, "p": (2, 4)}, "C": {"c": 2, "h": 3, "p": (6, 10)}, "D": {"c": 3, "h": 4, "p": (12, 18)}}
CLASSES = {"widebody": {"rev": 90, "w": 6, "pen": 400}, "narrowbody": {"rev": 50, "w": 4, "pen": 260},
           "regional": {"rev": 20, "w": 2, "pen": 30}}


def make(mode, seed, n, S=120):
    rng = random.Random(seed)
    inst = {"S": S, "bases": BASES, "shift_cost": 15,
            "classes": {k: dict(v) for k, v in CLASSES.items()},
            "types": {k: {"c": v["c"], "h": v["h"]} for k, v in TYPES.items()},
            "closed": {}, "nostart": {}, "checks": []}
    ids = rng.sample(range(10000, 99999), 4 * n + 1)
    k = 0
    tight = rng.choice(BASES) if mode == "hidden" else None
    twin = None
    for b in BASES:
        t = 1 + rng.randint(0, 3)
        nost = sorted(rng.sample(range(1, S + 1), S // 10))
        inst["nostart"][b] = nost
        for i in range(n):
            ty = rng.choices("ACD", weights=[3, 4, 2])[0]
            p = rng.randint(*TYPES[ty]["p"])
            cl = rng.choices(list(CLASSES), weights=[2, 3, 3])[0]
            ps = t
            while ps in nost:
                ps += 1
            due = ps + p - 1 + rng.randint(0, 4)
            r = ps
            if mode == "hidden" and rng.random() < 0.45:
                r = max(1, ps - rng.randint(1, 6))
            if mode == "hidden" and i == 1:
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
            # late regional heavy check whose slot is hit by a long closure
            ps = t
            while ps in nost:
                ps += 1
            p = rng.randint(12, 14)
            L = min(rng.randint(20, 24), S - ps - p)
            inst["checks"].append({"id": "Q%05d" % ids[k], "base": b, "cls": "regional", "type": "D", "p": p,
                                   "ps": ps, "due": ps + p - 1, "r": ps})
            k += 1
            inst["closed"][b] = list(range(ps + 1, ps + 1 + L))
        # disruption closure
        elif rng.random() < 0.8:
            c0 = rng.randint(10, max(11, min(S - 10, t - 10)))
            ln = rng.randint(3, 9) if b != tight else rng.randint(14, 22)
            inst["closed"][b] = list(range(c0, c0 + ln))
    return inst


if __name__ == "__main__":
    mode, seed, n, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    inst = make(mode, seed, n)
    inst["K"] = int(sys.argv[5]) if len(sys.argv) > 5 else 40
    json.dump(inst, open(out, "w"), indent=1)
