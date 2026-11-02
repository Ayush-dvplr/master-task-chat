"""Differential fuzz on the FINAL bundle generator (tests/test_output.py).

For each lever config, N fresh seeds: emit a corpus with the separating case of
that lever planted, run solution/solve.py (oracle), the one-lever reflex variant
and the a2 agent program, and compare every graded artifact byte for byte.
usage: python3 fuzz_final.py N OUT_JSON
"""
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/"
              "sensor-network-lsq-correlated-adjustment")
sys.path.insert(0, str(BUNDLE / "tests"))
import test_output as T  # noqa: E402
import variants as V  # noqa: E402

CONFIGS = {"A": {"closure": "sep"}, "B": {"chain": "deep"}, "C": {"mislabel": 24}}
GRADED = [a for a in T.ARTIFACT_NAMES]
PROGS: dict = {}


def init(folder):
    PROGS["oracle"] = V.build((), folder)
    for lv in "ABC":
        PROGS[lv] = V.build((lv,), folder)
    PROGS["a2"] = HERE.parent / "agent_program" / "derive_report.py"


def run_one(job):
    lever, seed = job
    base = T.corpus_config
    T.corpus_config = lambda s: base(s) | CONFIGS[lever]
    work = Path(tempfile.mkdtemp(prefix=f"fz-{lever}-"))
    try:
        try:
            T.emit_corpus(work / "data", seed)
        except AssertionError as exc:
            return {"lever": lever, "seed": seed, "reject": str(exc)[:80]}
        outs = {}
        for name in ("oracle", lever, "a2"):
            out = work / name
            p = subprocess.run([sys.executable, str(PROGS[name]), str(work / "data"), str(out)],
                               capture_output=True, timeout=120)
            outs[name] = (p.returncode, out)

        def differs(name):
            code, out = outs[name]
            if code != 0:
                return ["exit"]
            return [a for a in GRADED if not filecmp.cmp(outs["oracle"][1] / a, out / a, shallow=False)]
        return {"lever": lever, "seed": seed, "oracle_code": outs["oracle"][0],
                "reflex_diff": differs(lever), "a2_diff": differs("a2")}
    finally:
        T.corpus_config = base
        shutil.rmtree(work, ignore_errors=True)


def main():
    n = int(sys.argv[1])
    folder = Path(tempfile.mkdtemp(prefix="fz-progs-"))
    jobs = [(lv, 77_000_003 + 104_729 * i) for lv in "ABC" for i in range(n)]
    with Pool(9, initializer=init, initargs=(folder,)) as pool:
        recs = pool.map(run_one, jobs, chunksize=3)
    Path(sys.argv[2]).write_text(json.dumps(recs))
    for lv in "ABC":
        rs = [r for r in recs if r["lever"] == lv]
        ok = [r for r in rs if "reject" not in r]
        print(lv, "corpora", len(rs), "rejected", len(rs) - len(ok),
              "oracle_nonzero", sum(1 for r in ok if r["oracle_code"]),
              "reflex_differ", f"{sum(1 for r in ok if r['reflex_diff'])}/{len(ok)}",
              "a2_differ", f"{sum(1 for r in ok if r['a2_diff'])}/{len(ok)}")


if __name__ == "__main__":
    main()
