"""ref.solve against the template's exhaustive _enumerate (cost and tie-rule pick)."""
import random
import sys

import ref
import wide

tt = wide.load_template()
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
bad = done = ties = 0
for i in range(int(sys.argv[2]) if len(sys.argv) > 2 else 300):
    if i % 2:
        n = rng.randint(4, 9)
        P = tt._tiny_project(rng, n, rng.randint(1, min(4, n)), rng.randint(n, n + 6))
        # some charges equal to make ties likely
        for q in P["act"]:
            P["act"][q] = rng.randint(1, 3)
        for e in P["edges"]:
            P["edges"][e] = rng.randint(1, 4)
    else:
        P = wide.wide_project(rng, n_blocks=(2, 3), size=(5, 6), cold=(3, 4), density=(1.0, 1.2))
        if len(P["edges"]) > 17:
            continue
        for e in P["edges"]:
            P["edges"][e] = rng.randint(1, 6)
    proj = tt._as_project(P)
    if len(proj["links"]) > 17:
        continue
    want = tt._enumerate(proj)
    got = ref.solve(proj)
    done += 1
    ties += 1000 * (i % 2 == 0)
    if want is None or got is None:
        if (want is None) != (got is None):
            bad += 1
        continue
    ties += want[1] > 1
    if (want[0], want[2]) != tuple(got):
        bad += 1
        print("MISMATCH", i, want, got)
    elif (want[1] == 1) != ref.unique(proj, got):
        bad += 1
        print("UNIQUE MISMATCH", i, want[1])
print("checked", done, "with ties", ties, "mismatches", bad)
