"""Measure each program on the three long fresh months (in Docker): seconds, exit, and exact match of the lever documents.

Uses the bundle's own test module for the generator and reference engine; rewardkit is stubbed (only decorators used).
"""
import json
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

stub = types.ModuleType("rewardkit")
stub.criterion = lambda **kw: (lambda f: f)
stub.criteria = types.SimpleNamespace(__getattr__=None)


class _Criteria:
    def __getattr__(self, name):
        return lambda **kw: None


stub.criteria = _Criteria()
sys.modules["rewardkit"] = stub
sys.path.insert(0, "/tests")
import test_output as t  # noqa: E402

CAP = 180
programs = sys.argv[1:]
results = {}
for k in (1, 2, 3):
    files = t._long_files(k)
    want = t._expected("long-%d" % k, lambda: files)
    for prog in programs:
        work = Path(tempfile.mkdtemp(prefix="long-"))
        src = work / "extract"
        src.mkdir()
        for name, blob in files.items():
            (src / name).write_bytes(blob)
        out = work / "reports"
        cwd = work / "elsewhere"
        cwd.mkdir()
        start = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, "-I", prog, "--input", str(src), "--output", str(out)],
                                  cwd=str(cwd), capture_output=True, text=True, timeout=CAP)
            rc, err = proc.returncode, proc.stderr[-300:]
        except subprocess.TimeoutExpired:
            rc, err = None, "timed out at %d s" % CAP
        secs = time.monotonic() - start
        docs = {}
        if rc == 0:
            for name in ("normalized.jsonl", "summary.json", "product_summary.json"):
                try:
                    found = t._first_diff(want[name], t._load(out, name))
                except Exception as exc:  # unreadable document
                    found = "unreadable: %s" % exc
                docs[name] = "exact" if found is None else ("WRONG " + found)[:300]
        row = {"k": k, "program": Path(prog).name, "seconds": round(secs, 2), "returncode": rc,
               "stderr_tail": err.strip().splitlines()[-1:] if err else [], "docs": docs}
        print(json.dumps(row), flush=True)
