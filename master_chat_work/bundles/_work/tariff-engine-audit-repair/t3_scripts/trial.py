import random, time
from vouch import *
rng = random.Random(5)
bad = 0
for t in range(300):
    T = rng.randint(0, 3000); n = rng.randint(0, 9)
    vs = [("V%d" % rng.randint(1, 60), rng.choice([rng.randint(1, 1500), 100*rng.randint(1, 15)])) for _ in range(n)]
    vs = list({v: (v, a) for v, a in vs}.values())
    r = ref(T, vs); nv = naive(T, vs); d = dictdp(T, vs); ar = arraydp(T, vs)
    if not (r == nv == d == ar):
        bad += 1; print(T, vs, r, nv, d, ar)
print("small bad", bad)
def big(T, n):
    vs = []
    for i in range(n):
        if rng.random() < 0.6: a = 500 * rng.randint(1, max(1, T // 2000))
        else: a = rng.randint(T // 50, T // 5)
        vs.append(("V%d" % rng.randint(1, 9999), a))
    return list({v: (v, a) for v, a in vs}.values())
for T, n in [(40000, 40), (90000, 80), (100000, 110)]:
    vs = big(T, n)
    t0 = time.time(); r = ref(T, vs); t1 = time.time()
    g = greedy(T, vs); t2 = time.time()
    ar = arraydp(T, vs); t3 = time.time()
    print(T, n, "ref %.3f" % (t1-t0), "array %.2f" % (t3-t2), "sum", sum(dict(vs)[x] for x in r), "k", len(r), "greedy sum", sum(dict(vs)[x] for x in g), len(g), "same", r == ar, g == r)
    if n <= 80:
        t0 = time.time(); d = dictdp(T, vs); print("  dict %.2f" % (time.time()-t0), d == r)
