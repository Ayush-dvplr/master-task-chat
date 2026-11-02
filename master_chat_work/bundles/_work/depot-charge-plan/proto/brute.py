"""Brute-force check of the reference on tiny instances: enumerate every plan, order by the stated
lexicographic key, compare the unique best with core.solve_flow. Usage: brute.py <n_instances>"""
import itertools, random, sys
sys.path.insert(0, "/p")
import core

DEP = core.DEPOTS


def tiny(seed):
    rng = random.Random(seed)
    S = 5
    price = [rng.choice([2, 2, 3]) for _ in range(S)]
    buses = []
    for i in range(rng.randint(2, 3)):
        a = rng.randint(0, 2)
        e = rng.randint(a + 1, S)
        rate = rng.randint(1, 2)
        pub = {}
        for s in range(a, e):
            if rng.random() < 0.4:
                pub[str(s)] = rng.randint(1, rate)
        buses.append({"id": "B%d" % (10 + i), "depot": rng.choice(DEP[:2]), "a": a, "e": e,
                      "need": rng.randint(1, 4), "rate": rate, "w": rng.choice([1, 4]), "pub": pub})
    cap = {d: [rng.randint(1, 3) for _ in range(S)] for d in DEP}
    feeder = [rng.randint(1, 4) for _ in range(S)]
    return {"S": S, "price": price, "feeder": feeder, "cap": cap, "buses": buses}


def key_of(inst, x):
    unmet = cost = moved = 0
    for b in inst["buses"]:
        got = sum(x.get((b["id"], s), 0) for s in range(inst["S"]))
        unmet += b["w"] * (b["need"] - got)
        for s, p in b["pub"].items():
            moved += max(0, min(p, b["rate"]) - x.get((b["id"], int(s)), 0))
    for (bid, s), k in x.items():
        cost += k * inst["price"][s]
    vec = [-x.get((b, s), 0) for s, b in sorted((s, b["id"]) for b in inst["buses"] for s in range(inst["S"]))]
    return (unmet, cost, moved, vec)


def brute(inst):
    vars_ = [(b, s) for b in inst["buses"] for s in range(b["a"], b["e"])]
    best = None
    bestx = None
    nbest = 0
    for vals in itertools.product(*[range(b["rate"] + 1) for b, s in vars_]):
        x = {}
        for (b, s), v in zip(vars_, vals):
            if v:
                x[(b["id"], s)] = v
        try:
            core.check_feasible(inst, x)
        except AssertionError:
            continue
        k = key_of(inst, x)
        if best is None or k < best:
            best, bestx, nbest = k, x, 1
        elif k == best:
            nbest += 1
    return bestx, best, nbest


n = int(sys.argv[1])
bad = 0
for seed in range(n):
    inst = tiny(seed)
    bx, bk, nb = brute(inst)
    rx = core.solve_flow(inst)
    if rx != bx or nb != 1:
        bad += 1
        print("MISMATCH seed", seed, bk, key_of(inst, rx), nb)
print("BRUTE checked", n, "mismatches", bad)
print("ALL_DONE")
