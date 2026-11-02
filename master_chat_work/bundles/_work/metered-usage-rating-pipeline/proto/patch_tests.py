"""Scratch: patch a copy of tests/test_output.py into proto/t_proto.py (prototype of the build edits)."""
import sys
SRC = sys.argv[1]
s = open(SRC, encoding="utf-8").read()

old_ref = """    for acct in parent_of:
        top = acct
        while parent_of[top]:
            top = parent_of[top]
        group_of[acct] = top
"""
new_ref = """    for acct in parent_of:
        path = []
        top = acct
        while top not in group_of and parent_of[top]:
            path.append(top)
            top = parent_of[top]
        top = group_of.get(top, top)
        for member in path:
            group_of[member] = top
        group_of[acct] = top
"""
assert s.count(old_ref) == 1
s = s.replace(old_ref, new_ref)

old_sig = "def gen_month(seed, month, rows_per_collector, n_accounts, hidden, compute):"
assert s.count(old_sig) == 1
s = s.replace(old_sig, "def gen_month(seed, month, rows_per_collector, n_accounts, hidden, compute, chain=0):")

old_depth = """        depth = {}
        for a in order:
            d, top = 0, a
            while parent[top]:
                d, top = d + 1, parent[top]
            depth[a] = d
"""
new_depth = """        if chain:
            # one long reseller line: own rng so the groups above do not move
            crng = _gen_random.Random(seed * 104729 + 29)
            rest = free_heavy + free_light
            crng.shuffle(rest)
            line = rest[:chain]
            assert len(line) == chain, "chain"
            for i in range(1, chain):
                up = line[i - 1] if crng.random() < 0.97 else line[crng.randrange(max(0, i - 4), i)]
                parent[line[i]] = up
                parent_text[line[i]] = _gen_variant(crng, up) if crng.random() < 0.5 else up
        depth = {}
        for a in order:
            path, top = [], a
            while top not in depth and parent[top]:
                path.append(top)
                top = parent[top]
            d = depth.setdefault(top, 0)
            for member in reversed(path):
                d += 1
                depth[member] = d
        if chain:
            assert max(depth.values()) >= chain * 9 // 10, "chain depth"
"""
assert s.count(old_depth) == 1
s = s.replace(old_depth, new_depth)
old_w = "    weights = [12 if a in heavy else 1 for a in normal]\n"
assert s.count(old_w) == 1
s = s.replace(old_w, old_w + "    cum_weights, run_total = [], 0\n    for w in weights:\n        run_total += w\n        cum_weights.append(run_total)\n")
assert s.count("rng.choices(normal, weights)[0]") == 2
s = s.replace("rng.choices(normal, weights)[0]", "rng.choices(normal, cum_weights=cum_weights)[0]")
s = s.replace("RUN_LIMIT_SEC = 600", "RUN_LIMIT_SEC = 60")
open(sys.argv[2], "w", encoding="utf-8").write(s)
print("patched ->", sys.argv[2])
