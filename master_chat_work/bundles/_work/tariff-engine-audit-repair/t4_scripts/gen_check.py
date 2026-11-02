"""Build the 7 ledger corpora, print balances, voucher counts, attempt, timing."""
import sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "t3_scripts"))
from load import load
m = load()
for corpus in ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
    t = time.time()
    texts = m._ledger_texts(corpus)
    t1 = time.time()
    want = m._ledger_want(corpus)
    t2 = time.time()
    rows, bal = m._voucher_rows(texts), m._balances(texts)
    big = [(a, bal[a], len(v)) for a, v in rows.items() if bal.get(a, 0) > 10**9]
    print(corpus, "gen %.1fs ref %.2fs" % (t1 - t, t2 - t1), big, "accounts", len(want), flush=True)
