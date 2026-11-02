"""Docker only (python3 -B, /tests = BUNDLE tests, /w = WORK/h1_a1 read-only).

usage: python3 -B witness_check.py OUTLOG
1. Reference seconds: for every held-out folder (HIDDEN and FORMS) rebuild it in a temp dir with
   the tests' own generator and time one derive() on the plain folder (before any Word reform).
2. Named difference: run the a1 program and the oracle on each saved witness folder
   /w/witness/<hN>/data and report the first differing field against /w/witness/<hN>/want.json.
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402

def run(prog, data):
    out = Path(tempfile.mkdtemp())
    t = time.time()
    p = subprocess.run(["python3", "-B", prog, str(data), str(out)], capture_output=True, text=True, timeout=60)
    secs = time.time() - t
    if p.returncode != 0:
        return None, secs, p.stderr.strip().splitlines()[-1:] or ["rc %d" % p.returncode]
    got = {n: json.loads((out / n).read_text()) for n in T.ARTIFACT_NAMES}
    return got, secs, None


def main():
    log = open(sys.argv[1], "w")
    for name in list(T.HIDDEN) + list(T.FORMS):
        root = Path(tempfile.mkdtemp())
        data = root / "data"
        data.mkdir()
        if name in T.HIDDEN:
            seed, empty, stype, x1 = T.HIDDEN[name]
        else:
            seed, empty, stype, x1 = T.FORMS[name][0], False, "bind", False
        T._planted_corpus(name, seed, empty, stype, x1, data)
        t = time.time()
        T.derive(str(data))
        rec = {"name": name, "ref_s": round(time.time() - t, 2)}
        wit = Path("/w/witness") / name
        if wit.is_dir():
            want = json.loads((wit / "want.json").read_text())
            for label, prog in (("a1", "/w/a1_program.py"), ("oracle", "/sol/solve.py")):
                got, secs, err = run(prog, wit / "data")
                diff = err or next((d for n in T.ARTIFACT_NAMES
                                    for d in [T._first_diff(got[n], want[n], n)] if d), "EXACT")
                rec[label] = {"s": round(secs, 2), "first_diff": diff}
        log.write(json.dumps(rec) + "\n")
        log.flush()
    log.write("ALL_DONE\n")


if __name__ == "__main__":
    main()
