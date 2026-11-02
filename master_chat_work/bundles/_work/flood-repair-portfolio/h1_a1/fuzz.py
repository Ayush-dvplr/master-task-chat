"""Fuzz a program against the verifier reference on small generated books.

usage: python3 -B fuzz.py PROGRAM SEED0 COUNT
Prints one line per book: seed spec-tag MATCH|DIFF <first difference>|FAIL <rc>.
"""
import json
import random
import subprocess
import sys
import tempfile
import types
from pathlib import Path

stub = types.ModuleType("rewardkit")
class _Any:
    def __getattr__(self, name):
        return lambda *a, **k: None


stub.criteria = _Any()
stub.criterion = lambda *a, **k: (lambda f: f)
sys.modules["rewardkit"] = stub
sys.path.insert(0, "/b/tests")
import test_output as T  # noqa: E402

prog, seed0, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for seed in range(seed0, seed0 + count):
    r = random.Random(seed)
    k = r.randint(0, 3)
    spec = {"audit_large": r.choice([0, 10, 60]), "audit_small": r.choice([0, 5, 12]),
            "blank_row": r.choice([0, 50]), "crews": 300 + 60 * k, "faults": r.randint(0, 19),
            "order": r.choice(["shuffle", "fixed"]), "permits": 300 + 80 * k,
            "sites": 300 + 60 * k, "small": r.randint(20, 60), "ties": 2 * r.randint(0, 6),
            "large": [(r.randint(20, 60), r.randint(3, 8)) for _ in range(k)]}
    spec["faults"] = min(spec["faults"], spec["small"] - spec["ties"])
    tag = "k%d f%d s%d t%d" % (k, spec["faults"], spec["small"], spec["ties"])
    try:
        files, _ = T.make_book(10_000 + seed, spec)
    except (AssertionError, ValueError) as exc:
        print(seed, tag, "GENFAIL", type(exc).__name__, exc)
        continue
    want = T._Ledger(files).documents()
    with tempfile.TemporaryDirectory() as td:
        data = T._write_book(Path(td) / "book", files)
        out = Path(td) / "out"
        proc = subprocess.run([sys.executable, "-I", "-S", prog, str(data), str(out)],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            print(seed, tag, "FAIL", proc.returncode, proc.stderr.strip()[-200:].replace("\n", " | "))
            continue
        bad = None
        for name in T.ARTIFACT_NAMES:
            got = json.loads((out / name).read_text())
            found = T.first_difference(got, want[name])
            if found:
                bad = "%s %s got=%s want=%s" % (name, found, str(got)[:0], "")
                break
        print(seed, tag, "MATCH" if bad is None else "DIFF " + bad, flush=True)
print("ALL_DONE")
