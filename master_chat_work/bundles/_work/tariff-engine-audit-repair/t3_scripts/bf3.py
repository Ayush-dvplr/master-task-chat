"""Round-3 BRANCH_FIRE: per corpus, statement counts and which statement branches fire."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load import load  # noqa: E402
from vouch import greedy  # noqa: E402

m = load()
ROWS = []


def optimal_sets(target, vouchers, cap=2):
    """number of distinct voucher sets reaching the optimum (capped), None when too large to count"""
    if target > 60_000:
        return None
    ways = {0: 1}
    for _, cents in vouchers:
        for total, count in list(ways.items()):
            grown = total + cents
            if grown <= target:
                ways[grown] = min(cap, ways.get(grown, 0) + count)
    return ways[max(ways)]


for corpus in ["shipped", "fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"]:
    texts = m._statement_texts_of(corpus)
    vouchers = m._voucher_rows(texts)
    balances = m._balances(texts)
    raw = {}
    ledger = m._Ledger(texts)
    for invoice in ledger.document()["invoices"]:
        raw.setdefault(invoice["account"], 0)
    c = Counter()
    for account, items in vouchers.items():
        target = balances.get(account, 0)
        best = m._redeem(target, items)
        c["statements"] += 1
        c["big (balance > 1,000,000 cents)"] += target > 1_000_000
        c["no voucher fits"] += not best
        c["balance clamped to 0"] += target == 0
        c["greedy differs"] += sorted(greedy(target, items)) != best
        ids = sorted(v for v, _ in items)
        c["string order != numeric order"] += ids != sorted(ids, key=lambda v: (len(v), v))
        n = optimal_sets(target, items)
        c["tie (>= 2 optimal sets)"] += n is not None and n >= 2
        fewest = None
        c["paid amount present"] += any(k[0] == account for k in ledger.paid)
    ROWS.append((corpus, c))

keys = sorted({k for _, c in ROWS for k in c})
print("| branch | " + " | ".join(corpus for corpus, _ in ROWS) + " |")
print("|---|" + "---|" * len(ROWS))
for key in keys:
    print(f"| {key} | " + " | ".join(str(c[key]) for _, c in ROWS) + " |")
