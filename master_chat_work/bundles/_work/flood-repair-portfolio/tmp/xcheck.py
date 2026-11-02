import sys, os, json, time, itertools
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, W); sys.path.insert(0, os.path.join(W, "proto"))
import solve_draft as S, mw
book = S.load(sys.argv[1])
ordered = S.build(book)
meta = json.load(open(sys.argv[1] + "_meta.json"))
large = {x["round"] for x in meta["large"]}
bad = 0
for r in ordered:
    if r.fault: continue
    ids = sorted(r.ids); n = len(ids); idx = {p: i for i, p in enumerate(ids)}
    W_ = [r.detail[p]["benefit"] * (1 << n) + (1 << (n - 1 - i)) for i, p in enumerate(ids)]
    adj = [0] * n
    for a, b in r.pairs:
        adj[idx[a]] |= 1 << idx[b]; adj[idx[b]] |= 1 << idx[a]
    t = time.time()
    if n <= 22:
        best = None
        for m in range(1 << n):
            ok = all(not (m >> i & 1) or not (adj[i] & m) for i in range(n))
            if ok:
                v = sum(W_[i] for i in range(n) if m >> i & 1)
                if best is None or v > best[0]: best = (v, m)
        want = sorted(ids[i] for i in range(n) if best[1] >> i & 1)
    else:
        order = None
        val, mask, st = mw.ref_solve(n, W_, adj, order)
        want = sorted(ids[i] for i in range(n) if mask >> i & 1)
    if want != r.selected:
        bad += 1; print("DIFF", r.rid, n)
    if r.rid in large: print("large", r.rid, n, len(r.pairs), "sel", len(r.selected), "total", r.total, "check", round(time.time()-t, 2))
print("bad", bad)
