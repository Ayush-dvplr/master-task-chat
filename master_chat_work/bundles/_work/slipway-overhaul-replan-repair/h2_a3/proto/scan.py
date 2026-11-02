"""Scan held-out seeds. usage: python3 -B scan.py <outdir> <n> <variant...>
variant is a comma list of places or 'plain'. Prints one line per seed and
variant: seed variant ok|abort reason seconds; then ALL_DONE."""
import json
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_output as T  # noqa: E402

OUT = Path(sys.argv[1])
N = int(sys.argv[2])
VARIANTS = sys.argv[3:]


def one(arg):
    i, variant = arg
    seed = T.child_seed(20261101, "scan" + str(i))
    legacy = () if variant == "plain" else tuple(variant.split(","))
    t0 = time.time()
    try:
        d = Path(tempfile.mkdtemp())
        root = T.write_corpus(d / "c", seed, legacy)
        o = Path(tempfile.mkdtemp())
        T.ref_publish(root, o, ())
        return (i, seed, variant, "ok", "", round(time.time() - t0, 2))
    except SystemExit as exc:
        return (i, seed, variant, "abort", str(exc), round(time.time() - t0, 2))
    except Exception as exc:  # recorded, the scan keeps going
        return (i, seed, variant, "error", repr(exc)[:200],
                round(time.time() - t0, 2))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(i, v) for i in range(N) for v in VARIANTS]
    rows = []
    with Pool(2) as pool:
        for r in pool.imap(one, jobs):
            rows.append(r)
            print(*r, flush=True)
    (OUT / "scan.json").write_text(json.dumps(rows, indent=1))
    print("ALL_DONE")
