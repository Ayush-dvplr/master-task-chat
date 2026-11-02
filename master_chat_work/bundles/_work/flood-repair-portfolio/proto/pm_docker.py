"""Premortem: every solver on every planned hidden instance under the stated per-round limit."""
import json, random, sys, time, mw, gen
from variants_lib import memo_rule
LIM = float(sys.argv[1]) if len(sys.argv) > 1 and __name__ == "__main__" else 10.0
DIAG = float(sys.argv[2]) if len(sys.argv) > 2 and __name__ == "__main__" else 0.7
PLAN = [(1, 160, 14), (2, 152, 13), (3, 144, 12), (4, 160, 13), (5, 148, 14), (6, 156, 12)]

def instance(seed, n, rows):
    r = random.Random(seed * 7919)
    n_, w, cl, pr = gen.grid(r, n, rows=rows, wlo=90, whi=110, diag=DIAG, tri=1)
    perm = list(range(n_)); r.shuffle(perm)
    w2 = [0] * n_
    for i in range(n_): w2[perm[i]] = w[i]
    pr2 = [(perm[a], perm[b]) for a, b in pr]
    W = mw.tiebreak_weights(w2, list(range(n_)))
    return n_, W, mw.build_adj(n_, [], pr2), pr2

def lp_round(n, W, adj, pairs):
    from scipy.optimize import linprog
    import numpy as np
    tri = set()
    for a, b in pairs:
        for c in mw.bits(adj[a] & adj[b]):
            tri.add(tuple(sorted((a, b, c))))
    rows = [list(t) for t in tri] + [[a, b] for a, b in pairs]
    A = np.zeros((len(rows), n))
    for i, rr in enumerate(rows):
        for v in rr: A[i, v] = 1
    res = linprog(-np.array([float(x >> n) for x in W]), A_ub=A, b_ub=np.ones(len(rows)), bounds=(0, 1), method="highs")
    x = res.x
    assert x is not None, res.message
    S = 0
    for v in sorted(range(n), key=lambda v: -x[v]):
        if not (adj[v] & S): S |= 1 << v
    return S

if __name__ == "__main__":
    out = []
    for seed, n, rows in PLAN:
        n_, W, adj, pairs = instance(seed, n, rows)
        t = time.time(); rv, rs, st = mw.ref_solve(n_, W, adj); tref = time.time() - t
        sh = n_  # tiebreak shift
        loss = lambda S: (rv - mw.weight_of(W, S)) >> sh
        row = {"seed": seed, "n": n_, "rows": rows, "edges": len(pairs), "t_ref": round(tref, 3), "states": st, "opt": rv >> sh}
        row["greedy_w"] = loss(mw.greedy(n_, W, adj, "w"))
        row["greedy_ratio"] = loss(mw.greedy(n_, W, adj, "ratio"))
        row["local_swap"] = loss(mw.local_search(n_, W, adj, mw.greedy(n_, W, adj, "w"), two=True))
        S = mw.ils(n_, W, adj, LIM, seed=seed); row["ils_limit"] = "OK" if S == rs else loss(S)
        try:
            S = lp_round(n_, W, adj, pairs); row["lp_round_ls"] = loss(mw.local_search(n_, W, adj, S, two=True)); row["lp_round"] = loss(S)
        except ImportError:
            row["lp_round"] = "no scipy"
        t = time.time(); ok, v, S, c = mw.bnb_classic(n_, W, adj, LIM)
        row["bnb_colour"] = ("cert %.1fs" % (time.time() - t)) if ok else "TO inc_loss=%s" % (loss(S) if S else "none")
        t = time.time(); ok, v, S, c = mw.bnb_memo(n_, W, adj, LIM)
        row["bnb_memo_reduce_split"] = ("cert %.1fs" % (time.time() - t)) if ok else "TO"
        for rule in ("low", "mindeg"):
            t = time.time(); ok, v, S, c = memo_rule(n_, W, adj, LIM, rule)
            row["memo_" + rule] = ("cert %.1fs" % (time.time() - t)) if ok else "TO"
        print(json.dumps(row), flush=True)
    print("ALL_DONE", flush=True)
