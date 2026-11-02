"""fixed_repo task.core against _enumerate (small, both methods) and old span-4 _optimum."""
import random
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "fixed_repo/src"))
from task import core, parser  # noqa: E402
import wide  # noqa: E402

tt = wide.load_template()
REAL = core._subsets_cheaper


def as_pkg(proj):
    n = proj["n"]
    roles = ["depot"] + ["cold_room" if p in proj["cold"] else "relay" for p in range(1, n + 1)]
    return parser.Project("P", ["S%d" % p for p in range(n + 1)], roles, [None] * (n + 1),
                          list(proj["charge"]), sorted(proj["links"]), len(proj["links"]))


def solve(proj):
    p = as_pkg(proj)
    if any(c not in reach(proj) for c in proj["cold"]):
        return None
    net = core.best_network(p)
    return net.quote, list(net.links), core.unique(p)


def reach(proj):
    adj = {}
    for _l, a, b, _c in proj["links"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, todo = {0}, [0]
    while todo:
        for u in adj.get(todo.pop(), []):
            if u not in seen:
                seen.add(u)
                todo.append(u)
    return seen


mode, seed = sys.argv[1], int(sys.argv[2])
bad = done = 0
if mode == "small":
    rng = random.Random(seed)
    for i in range(int(sys.argv[3])):
        if i % 2:
            n = rng.randint(4, 9)
            P = tt._tiny_project(rng, n, rng.randint(1, min(4, n)), rng.randint(n, n + 6))
            for q in P["act"]:
                P["act"][q] = rng.randint(1, 3)
            for e in P["edges"]:
                P["edges"][e] = rng.randint(1, 4)
        else:
            P = wide.wide_project(rng, n_blocks=(2, 3), size=(5, 6), cold=(3, 4), density=(1.0, 1.2))
            for e in P["edges"]:
                P["edges"][e] = rng.randint(1, 6)
        proj = tt._as_project(P)
        if len(proj["links"]) > 17:
            continue
        want = tt._enumerate(proj)
        for force in (False, True):
            core._subsets_cheaper = lambda *a, f=force: f
            got = solve(proj)
            done += 1
            if (want is None) != (got is None):
                bad += 1
                print("NONE MISMATCH", i, force)
                continue
            if want is None:
                continue
            if (want[0], list(want[2])) != tuple(got[:2]) or (want[1] == 1) != got[2]:
                bad += 1
                print("MISMATCH", i, force, want, got)
    core._subsets_cheaper = REAL
else:
    worst = 0.0
    for k in range(int(sys.argv[3])):
        rng = random.Random(seed * 7 + k)
        for _ in range(4):
            n = rng.randint(37, 51)
            P = tt._hub_project(rng, n, rng.randint(16, 17), rng.randint(65, 92), rng.randint(3, 6))
            proj = tt._as_project(P)
            old = tt._optimum(proj)
            t = time.time()
            got = solve(proj)
            worst = max(worst, time.time() - t)
            done += 1
            if old is None or got is None:
                bad += (old is None) != (got is None)
                continue
            if old[0] != got[0] or (old[1] == 1) != got[2] or (got[2] and list(old[2]) != got[1]):
                bad += 1
                print("MISMATCH", k, old[:2], got[0], got[2])
    print("worst secs", round(worst, 3))
print("checked", done, "mismatches", bad)
