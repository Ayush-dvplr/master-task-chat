import random, sys
import mw, gen

fams = [lambda r, n: gen.band(r, n, bw=6), lambda r, n: gen.ring(r, n, bw=5), lambda r, n: gen.grid(r, n, rows=3),
        lambda r, n: gen.motifs(r, n, k=6, ports=2, links=2), lambda r, n: gen.random_sparse(r, n, deg=4)]
bad = 0
for seed in range(300):
    r = random.Random(seed)
    n = r.randint(8, 20)
    n, w, cl, pr = fams[seed % len(fams)](r, n)
    # tie-heavy weights half the time
    if seed % 2:
        w = [r.choice([5, 6, 7]) for _ in range(n)]
    perm = list(range(n)); r.shuffle(perm)
    rank = perm
    W = mw.tiebreak_weights(w, rank)
    adj = mw.build_adj(n, cl, pr)
    bv, bs = mw.brute(n, W, adj)
    rv, rs, _ = mw.ref_solve(n, W, adj)
    ok1, cv, cs, _ = mw.bnb_classic(n, W, adj, 10)
    ok2, mv, ms, _ = mw.bnb_memo(n, W, adj, 10)
    for name, v, s in (("ref", rv, rs), ("classic", cv, cs), ("memo", mv, ms)):
        if v != bv or s != bs or not mw.is_independent(adj, s):
            bad += 1
            print("MISMATCH", seed, name, v, bv, bin(s), bin(bs))
print("bad", bad)
