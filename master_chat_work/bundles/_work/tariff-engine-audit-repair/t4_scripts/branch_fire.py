"""Wave-1 BRANCH_FIRE counts per ledger corpus (statements, big, balance 0, greedy differs, small-account ties)."""
import sys
from itertools import combinations
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "t3_scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "proto"))
from load import load
from solvers import SOLVERS
m = load()
for corpus in ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
    texts = m._ledger_texts(corpus)
    rows, bal = m._voucher_rows(texts), m._balances(texts)
    big = zero = differs = ties = 0
    for account, vouchers in rows.items():
        b = bal.get(account, 0)
        want = m._redeem_split(b, vouchers)
        if sorted(SOLVERS["greedy"](b, vouchers)) != sorted(want):
            differs += 1
        if b > 10**9:
            big += 1
        elif b == 0:
            zero += 1
        else:
            best = sum(c for v, c in vouchers if v in want)
            n = sum(1 for k in range(len(vouchers) + 1) for s in combinations(vouchers, k)
                    if sum(c for _, c in s) == best)
            ties += n > 1
    print(f"{corpus}: statements {len(rows)}, big {big}, balance 0 {zero}, small-account ties {ties}, greedy differs {differs}")
