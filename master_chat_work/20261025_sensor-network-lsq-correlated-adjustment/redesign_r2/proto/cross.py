"""Independence: in a corpus that plants lever X, the reflex of every other
lever must give the oracle's answer (W5 analogue for hidden extracts), and in
the shipped seed no reflex may change anything.
Usage: python3 cross.py N
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fuzz as F  # noqa: E402
import oracle_r2 as R  # noqa: E402

T = R.T


def same(a, b) -> bool:
    return (a["vtpv"] == b["vtpv"] and list(a["residuals"]) == list(b["residuals"])
            and [o.region for o in a["obs"]] == [o.region for o in b["obs"]]
            and list(a["weights_final"]) == list(b["weights_final"]))


def main():
    n = int(sys.argv[1])
    bad = []
    seeds = [(T.SAMPLE_SEED, "shipped", dict(closure="nonsep", chain="depth1", mislabel=0))]
    for i in range(n):
        s = 10_000_019 + 7919 * i
        seeds += [(s, "A", dict(closure="sep", chain="depth1", mislabel=0)),
                  (s, "B", dict(closure="nonsep", chain="deep", mislabel=0)),
                  (s, "C", dict(closure="nonsep", chain="depth1", mislabel=24))]
    for seed, planted, feats in seeds:
        work = Path(tempfile.mkdtemp(prefix="cross-", dir=F.SCRATCH))
        root = work / "data"
        try:
            R.emit_r2(root, seed, **feats)
            ref = R.solve_r2(root, F.ALL_OK)
            for lever in "ABC":
                if lever == planted:
                    continue
                modes = dict(F.ALL_OK)
                modes[lever] = "reflex"
                if not same(ref, R.solve_r2(root, modes)):
                    bad.append((seed, planted, lever))
        finally:
            shutil.rmtree(work, ignore_errors=True)
    print(f"corpora={len(seeds)} cross_differences={len(bad)} {bad[:10]}")


if __name__ == "__main__":
    main()
