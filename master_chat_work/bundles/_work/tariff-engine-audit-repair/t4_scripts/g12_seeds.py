"""G12: 300 seeds of the ledger generator; every one must build within 40 attempts with all asserts."""
import random, sys, time, collections
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "t3_scripts"))
from load import load
m = load()
corpora = ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed")
attempts = collections.Counter(); lo, hi, slow = 10**12, 0, 0.0
start = time.time()
for seed in range(300):
    corpus = corpora[seed % 7]
    texts, labels = m._quiet_corpus(corpus)
    for attempt in range(40):
        rng = random.Random((10_000 + seed) * 59 + 31 + 1000003 * attempt)
        try:
            planted, copies, over = m._ledger_once(texts, labels, rng, *m._LEDGER_LEVER[corpus])
            m._assert_ledger(texts, planted, copies, over)
            break
        except AssertionError:
            continue
    else:
        raise SystemExit(f"seed {seed} {corpus}: no build in 40 attempts")
    attempts[attempt] += 1
    bal = m._balances(planted)
    for a in copies:
        lo, hi = min(lo, bal[a]), max(hi, bal[a])
    t = time.time(); m._ledger_statements(planted); slow = max(slow, time.time() - t)
    if seed % 25 == 0:
        print(seed, "elapsed %.0fs" % (time.time() - start), flush=True)
print("seeds 300 ok; attempts histogram", dict(sorted(attempts.items())), "big balance range", lo, hi, "max ref %.2fs" % slow)
print("ALL_DONE")
