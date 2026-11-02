"""Item 7 (d11904c): add one shipped account whose vouchers are multiples of one face value plus a few odd
amounts below it, at shipped scale. Old rows stay; new rows are inserted at seeded positions."""
import random, sys
from math import gcd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "t3_scripts"))
from load import load, BUNDLE
m = load()
path = BUNDLE / "environment" / "ci" / "vouchers.csv"
old = path.read_text()
assert old.count("\n") == 199, "already added"
texts = m._shipped_texts(); texts["vouchers.csv"] = old
bal, rows = m._balances(texts), m._voucher_rows(texts)
rng = random.Random(20261028)
free = sorted(a for a, b in bal.items() if a not in rows and b > 30_000)
account = rng.choice(free)
B = bal[account]
for _ in range(1000):
    g, ns = rng.randrange(1_000, 3_000), rng.randrange(3, 5)
    small = [rng.randrange(g // (3 * ns), g // (ns + 1)) for _ in range(ns)]
    small[1] = small[0]
    if gcd(g, *small) == 1 and sum(small) // 3 <= B % g < sum(small):
        break
T = B // g
while True:
    units = [rng.randrange(1, 8) for _ in range(rng.randrange(8, 11))]
    units[rng.randrange(len(units))] = units[0]
    if 0.3 * sum(units) <= T <= 0.7 * sum(units):
        break
used = {int(v[1:]) for vs in rows.values() for v, _ in vs}
names = [f"V{n}" for n in rng.sample(sorted(set(range(1, 400)) - used), len(units) + len(small))]
new = list(zip(names, [u * g for u in units] + small))
chosen = set(m._redeem(B, new))
assert chosen == set(m._redeem_split(B, new))
picked = [(c, v in chosen) for v, c in new]
assert any(u and c % g == 0 for c, u in picked) and any(u and c % g for c, u in picked)
print("account", account, "balance", B, "face", g, "units", units, "small", small)
print("large tie", any(u and (c, False) in picked for c, u in picked if c % g == 0),
      "small tie", any(u and (c, False) in picked for c, u in picked if c % g))
lines = old.splitlines(keepends=True)
head, body = lines[0], lines[1:]
for v, c in new:
    body.insert(rng.randrange(len(body) + 1), f"{account},{v},{m._amount(c)}\n")
path.write_text(head + "".join(body))
print("redeemed", sorted(chosen), "due", m._amount(B - sum(c for v, c in new if v in chosen)))
