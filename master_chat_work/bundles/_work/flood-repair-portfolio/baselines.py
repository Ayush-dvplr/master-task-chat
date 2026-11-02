"""Run every baseline and generic exact solver on every planned round of a book.

python3 baselines.py BOOK_DIR LIMIT_EXACT LIMIT_ILS > rows.jsonl   (Docker image frp-premortem)
Each output line: {"round", "n", "large", "<method>": {"ids": [...], "exact": bool, "note": str}}
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "proto"))
import mw  # noqa: E402
import solve_draft as S  # noqa: E402
from pm_docker import lp_round  # noqa: E402
from variants_lib import reduce_bnb  # noqa: E402


def instance(rnd):
    ids = sorted(rnd.ids)
    n = len(ids)
    idx = {p: i for i, p in enumerate(ids)}
    W = [rnd.detail[p]["benefit"] * (1 << n) + (1 << (n - 1 - i)) for i, p in enumerate(ids)]
    adj = [0] * n
    pairs = []
    for a, b in rnd.pairs:
        adj[idx[a]] |= 1 << idx[b]
        adj[idx[b]] |= 1 << idx[a]
        pairs.append((idx[a], idx[b]))
    return ids, n, W, adj, pairs


def main():
    book_dir, lim, lim_ils = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    only_large = len(sys.argv) > 4 and sys.argv[4] == "large"
    book = S.load(book_dir)
    for rnd in S.build(book):
        if rnd.fault:
            continue
        ids, n, W, adj, pairs = instance(rnd)
        large = n > 40
        if only_large and not large:
            continue
        want = set(rnd.selected)
        row = {"round": rnd.rid, "n": n, "large": large}

        def rec(name, mask, note=""):
            got = sorted(ids[i] for i in range(n) if mask >> i & 1)
            row[name] = {"ids": got, "exact": set(got) == want, "note": note}

        g = mw.greedy(n, W, adj, "w")
        rec("greedy_w", g)
        rec("greedy_ratio", mw.greedy(n, W, adj, "ratio"))
        rec("local_swap", mw.local_search(n, W, adj, g, two=True))
        rec("ils", mw.ils(n, W, adj, lim_ils if large else 0.2, seed=7))
        x = lp_round(n, W, adj, pairs)
        rec("lp_round", x)
        rec("lp_round_ls", mw.local_search(n, W, adj, x, two=True))
        for name, fn in (("bnb_colour", lambda: mw.bnb_classic(n, W, adj, lim)),
                         ("bnb_memo_reduce_split", lambda: mw.bnb_memo(n, W, adj, lim)),
                         ("reduce_bnb", lambda: reduce_bnb(n, W, adj, lim))):
            t = time.time()
            ok, v, mask, c = fn()
            note = ("cert %.2fs" % (time.time() - t)) if ok else "TO"
            rec(name, mask or 0, note)
        print(json.dumps(row), flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
