import random, sys, json, mw, gen
import numpy as np
from scipy.optimize import linprog
def run(seed, n, rows, diag, tri, wlo, whi):
    r = random.Random(seed * 7919)
    n_, w, cl, pr = gen.grid(r, n, rows=rows, wlo=wlo, whi=whi, diag=diag, tri=tri)
    perm = list(range(n_)); r.shuffle(perm)
    w2 = [0]*n_
    for i in range(n_): w2[perm[i]] = w[i]
    pr = [(perm[a], perm[b]) for a, b in pr]
    W = mw.tiebreak_weights(w2, list(range(n_))); adj = mw.build_adj(n_, [], pr)
    rv, rs, st = mw.ref_solve(n_, W, adj)
    # maximal cliques of size 3 + edges not in any triangle; for king graph K4 too
    cons = set()
    for a, b in pr:
        com = mw.bits(adj[a] & adj[b])
        found = False
        for c in com:
            k4 = [d for d in mw.bits(adj[a] & adj[b] & adj[c])]
            if k4:
                for d in k4: cons.add(tuple(sorted((a, b, c, d))))
            else: cons.add(tuple(sorted((a, b, c))))
            found = True
        if not found: cons.add(tuple(sorted((a, b))))
    A = np.zeros((len(cons), n_))
    for i, t in enumerate(cons):
        for v in t: A[i, v] = 1
    res = linprog(-np.array(w2, float), A_ub=A, b_ub=np.ones(len(cons)), bounds=(0, 1), method="highs")
    x = res.x; frac = sum(1 for v in x if 1e-6 < v < 1-1e-6)
    S = 0
    for v in sorted(range(n_), key=lambda v: -x[v]):
        if not (adj[v] & S): S |= 1 << v
    sh = n_
    lsS = mw.local_search(n_, W, adj, S, True)
    return dict(seed=seed, diag=diag, tri=tri, deg=round(2*len(pr)/n_,1), states=st, opt=rv>>sh, lp=round(-res.fun,1), frac=frac,
                lp_loss=(rv-mw.weight_of(W,S))>>sh, lp_ls_loss=(rv-mw.weight_of(W,lsS))>>sh,
                ls_loss=(rv-mw.weight_of(W,mw.local_search(n_,W,adj,mw.greedy(n_,W,adj,"w"),True)))>>sh)
for diag, tri in [(1.0,1),(0.7,1),(0.5,1),(0.5,0),(0.3,0),(1.0,0)]:
    for seed in (1,2,3):
        print(json.dumps(run(seed,160,14,diag,tri,90,110)), flush=True)
print("ALL_DONE")
