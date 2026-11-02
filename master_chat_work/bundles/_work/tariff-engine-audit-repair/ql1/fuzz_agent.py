"""Differential fuzz: the QL-run agent package against the test reference on reseeded hidden corpora.

usage: python3 -B fuzz_agent.py ROUNDS [START]
Looks for WRONG output of the agent package (exact program) on stated rules; prints each divergence.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
AGENT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_tariff-engine-audit-repair/harden_r_ql1/agent_program/repo/src")
sys.path.insert(0, str(WORK / "rewardkit_stub"))
sys.path.insert(0, str(BUNDLE / "tests"))
os.environ.setdefault("APP_ROOT", str(BUNDLE / "environment"))
import test_output as t  # noqa: E402

CORPORA = ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed")


def agent(texts, statements=False):
    folder = Path(tempfile.mkdtemp(prefix="fz-"))
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8")
    cmd = [sys.executable, "-B", "-m", "tariff"] + (["--statements"] if statements else []) + [str(folder)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, PYTHONPATH=str(AGENT), PYTHONDONTWRITEBYTECODE="1"))
    if done.returncode:
        return {"rc": done.returncode, "err": done.stderr[-300:]}
    return json.loads(done.stdout)


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return f"{path}: {str(a)[:200]} != {str(b)[:200]}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: missing"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                ctx = a[i].get("account") if isinstance(a[i], dict) else ""
                return f"{d} (account {ctx})"
        return None if len(a) == len(b) else f"{path}: len {len(a)} != {len(b)}"
    return None if a == b else f"{path}: {a!r} != {b!r}"


def main():
    rounds = int(sys.argv[1])
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    base = (t.H1_SEED, t.H3_SEED, t.H5_SEED, t.H7_SEED)
    for k in range(start, start + rounds):
        t.H1_SEED, t.H3_SEED, t.H5_SEED, t.H7_SEED = (s + 7919 * k for s in base)
        t._QUIET_SEEDS.update({"fresh": t.H1_SEED, "rescaled": t.H1_SEED + 1, "relocated": t.H3_SEED,
                               "rotated": t.H3_SEED + 1, "api": t.H5_SEED, "recoded": t.H7_SEED,
                               "renamed": t.H7_SEED + 1})
        t._MEMO.clear()
        for corpus in CORPORA:
            try:
                texts = t._corpus_texts(corpus)
                ref = t._Ledger(texts).document()
            except Exception as error:  # generator could not settle this seed
                print(f"round {k} {corpus}: gen skip {type(error).__name__}", flush=True)
                continue
            got = agent(texts)
            d = first_diff(got, ref) if "rc" not in got else f"rc {got}"
            print(f"round {k} {corpus} invoices: {'ok' if not d else 'DIFF ' + d}", flush=True)
            try:
                stexts = t._statement_texts(corpus)
                sref = t._statements(stexts)
            except Exception as error:
                print(f"round {k} {corpus}: statement gen skip {type(error).__name__}", flush=True)
                continue
            sgot = agent(stexts, True)
            d = first_diff(sgot, sref) if "rc" not in sgot else f"rc {sgot}"
            print(f"round {k} {corpus} statements: {'ok' if not d else 'DIFF ' + d}", flush=True)


if __name__ == "__main__":
    main()
