"""usage: survey.py FAMILY N REPS SEED LIMIT key=val ..."""
import random, sys, time, json
import mw, gen

fam, n, reps, seed, limit = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
kw = {}
for a in sys.argv[6:]:
    k, v = a.split("=")
    kw[k] = float(v) if "." in v else int(v)
skip = set(kw.pop("skip", "") and [] or [])
for rep in range(reps):
    r = random.Random(seed * 1000 + rep)
    n_, w, cl, pr = getattr(gen, fam)(r, n, **kw)
    perm = list(range(n_)); r.shuffle(perm)
    W = mw.tiebreak_weights(w, perm)
    adj = mw.build_adj(n_, cl, pr)
    sh = n_
    deg = sum(mw.popcount(a) for a in adj) / n_
    t = time.time(); order = mw.elimination_order(n_, adj); t_ord = time.time() - t
    wid = mw.width_of(n_, adj, order)
    t = time.time(); rv, rs, ms = mw.ref_solve(n_, W, adj, order); t_ref = time.time() - t + t_ord
    g1 = mw.greedy(n_, W, adj, "w"); g2 = mw.greedy(n_, W, adj, "ratio")
    ls = mw.local_search(n_, W, adj, max((g1, g2), key=lambda s: mw.weight_of(W, s)))
    loss = lambda s: (rv - mw.weight_of(W, s)) >> sh
    row = dict(rep=rep, n=n_, deg=round(deg, 1), width=wid, states=ms, t_ref=round(t_ref, 2),
               opt=rv >> sh, g_w=loss(g1), g_r=loss(g2), ls=loss(ls))
    il = mw.ils(n_, W, adj, limit / 2, seed=rep)
    row["ils"] = "OK" if il == rs else loss(il)
    t = time.time(); ok, cv, cs, cn = mw.bnb_classic(n_, W, adj, limit, initial=ls)
    row["classic"] = ("%.1fs" % (time.time() - t)) if ok else (">%g inc_loss=%d nodes=%d" % (limit, (rv - cv) >> sh, cn))
    t = time.time(); ok, mv, msx, mn = mw.bnb_memo(n_, W, adj, limit)
    row["memo"] = ("%.1fs" % (time.time() - t)) if ok else (">%g nodes=%d" % (limit, mn))
    if ok:
        assert mv == rv, (mv, rv)
    print(json.dumps(row), flush=True)
