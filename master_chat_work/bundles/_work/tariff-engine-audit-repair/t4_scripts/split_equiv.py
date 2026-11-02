"""_redeem_split == r3 _redeem on shipped + r3 statement corpora + random small instances (incl. two-group shape)."""
import random, sys
from itertools import combinations
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "t3_scripts"))
from load import load
m = load()
bad = 0
for corpus in ("shipped", "fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
    texts = m._statement_texts_of(corpus)
    rows, bal = m._voucher_rows(texts), m._balances(texts)
    for a, v in rows.items():
        bad += m._redeem(bal.get(a, 0), v) != m._redeem_split(bal.get(a, 0), v)
    print(corpus, "bad", bad, flush=True)
def naive(target, vouchers):
    best = (0, ())
    items = sorted(vouchers)
    for r in range(len(items) + 1):
        for c in combinations(items, r):
            s = sum(x[1] for x in c)
            if s <= target and (s > best[0] or (s == best[0] and tuple(x[0] for x in c) < best[1])):
                best = (s, tuple(x[0] for x in c))
    return list(best[1])
rng = random.Random(5)
for trial in range(3000):
    n = rng.randrange(0, 12)
    ids = rng.sample(["K%d" % i for i in range(1, 200)] + ["V%d" % i for i in range(1, 50)], n)
    if trial % 2:
        g = rng.randrange(20, 60); ns = rng.randrange(0, 4) if n else 0
        amounts = [rng.randrange(1, 8) * g for _ in range(n - ns)] + [rng.randrange(1, max(2, g // (ns + 1))) for _ in range(ns)]
    else:
        amounts = [rng.randrange(1, 300) for _ in range(n)]
    if n > 1 and rng.random() < .5:
        amounts[1] = amounts[0]
    v = list(zip(ids, amounts))
    t = rng.randrange(0, sum(amounts) + 2)
    r1, r2, r3 = naive(t, v), m._redeem(t, v), m._redeem_split(t, v)
    if not (r1 == r2 == r3):
        bad += 1
        if bad < 4: print("MISMATCH", t, v, r1, r2, r3)
print("random bad", bad)
