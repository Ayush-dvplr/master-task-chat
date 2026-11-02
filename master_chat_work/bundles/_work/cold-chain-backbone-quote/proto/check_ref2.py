"""ref2 against _enumerate (small, both block methods) and against the old
span-4 _optimum on the old hidden fresh generator (cost, pick when unique, uniqueness)."""
import random
import sys
import time

import ref2
import wide

tt = wide.load_template()
mode = sys.argv[1]
seed = int(sys.argv[2])
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
        for dwmax in (False, True):
            ref2.FORCE = dwmax
            got = ref2.solve(proj)
            done += 1
            if (want is None) != (got is None):
                bad += 1
                print("NONE MISMATCH", i, dwmax)
                continue
            if want is None:
                continue
            if (want[0], want[2]) != tuple(got) or (want[1] == 1) != ref2.unique(proj, got):
                bad += 1
                print("MISMATCH", i, dwmax, want, got)
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
            got = ref2.solve(proj)
            if old is None or got is None:
                done += 1
                bad += (old is None) != (got is None)
                continue
            u = ref2.unique(proj, got)
            worst = max(worst, time.time() - t)
            done += 1
            if old[0] != got[0] or (old[1] == 1) != u or (u and list(old[2]) != list(got[1])):
                bad += 1
                print("MISMATCH", k, old[:2], got[0], u)
    print("worst solve+unique secs", round(worst, 3))
print("checked", done, "mismatches", bad)
