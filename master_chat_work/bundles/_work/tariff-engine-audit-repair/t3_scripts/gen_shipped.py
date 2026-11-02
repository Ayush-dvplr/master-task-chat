"""Write the shipped /app/ci/vouchers.csv (seeded, small instances)."""
import random, sys
sys.path.insert(0, '.')
from load import load, BUNDLE
m = load()
exec(open('stmt_block.py').read(), m.__dict__)
texts = m._shipped_texts()
bal = m._balances(texts)
rng = random.Random(20261027)
accounts = rng.sample(sorted(a for a, b in bal.items() if b > 0), 60)
ids = rng.sample(range(1, 400), 260)
rows = []
for k, account in enumerate(sorted(accounts)):
    t = bal[account]
    n = rng.randrange(1, 7)
    if k % 7 == 3:
        amounts = [rng.randrange(t + 1, t + 2000) for _ in range(n)]
    else:
        amounts = [rng.randrange(max(1, t // 5), t // 2 + 2) for _ in range(n)]
        if n >= 3 and k % 3 == 0:
            amounts[-1] = amounts[0] + amounts[1]
    for cents in amounts:
        rows.append((account, f"V{ids.pop()}", cents))
rng.shuffle(rows)
text = "account,voucher,amount\n" + "".join(f"{a},{v},{m._amount(c)}\n" for a, v, c in rows)
(BUNDLE / "environment" / "ci" / "vouchers.csv").write_text(text)
texts["vouchers.csv"] = text
import vouch
doc = m._statements(texts)["statements"]
rowsby = m._voucher_rows(texts)
gw = sum(vouch.greedy(m._balances(texts)[s["account"]], rowsby[s["account"]]) != s["redeemed"] for s in doc)
print(len(rows), "rows", len(doc), "statements; empty", sum(not s["redeemed"] for s in doc), "greedy wrong", gw)
