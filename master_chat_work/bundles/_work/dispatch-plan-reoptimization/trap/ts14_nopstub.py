#!/usr/bin/env python3
"""2c2361c TS-14 proof: full per-check results for nop (no solver.py) and stub (solver exits 0, writes nothing)."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade_local  # noqa: E402

STUB = "import sys\nfrom pathlib import Path\nPath(sys.argv[2]).mkdir(parents=True, exist_ok=True)\n"


def run(test_file, mode):
    with tempfile.TemporaryDirectory(prefix="dpr-ts14-") as tmp:
        app = Path(tmp) / "app"
        out = app / "out"
        out.mkdir(parents=True)
        if mode == "stub":
            (out / "solver.py").write_text(STUB)
        reg = grade_local.Registry()
        fake = types.ModuleType("rewardkit")
        fake.criteria = reg
        fake.criterion = lambda **kw: lambda f: f
        sys.modules["rewardkit"] = fake
        os.environ["APP_ROOT"] = str(app)
        spec = importlib.util.spec_from_file_location(f"t_{mode}_{abs(hash(test_file))}", test_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        got = {}
        for check in reg.weights:
            try:
                got[check] = bool(getattr(mod, check)(app))
            except Exception as exc:
                got[check] = f"error {exc!r}"
        pos = sum(w for w in reg.weights.values() if w > 0)
        earned = sum(w for c, w in reg.weights.items() if w > 0 and got[c] is True)
        pen = sum(w for c, w in reg.weights.items() if w < 0 and got[c] is True)
        return dict(mode=mode, earned=earned, penalty=pen, positive=pos, checks=got)


def main():
    before, after, output = sys.argv[1:4]
    res = {}
    for mode in ("nop", "stub"):
        b = run(str(Path(before).resolve()), mode)
        a = run(str(Path(after).resolve()), mode)
        res[mode] = dict(before=b, after=a, identical=b["checks"] == a["checks"])
        print(mode, b["earned"], b["penalty"], a["earned"], a["penalty"], res[mode]["identical"], flush=True)
    Path(output).write_text(json.dumps(res, indent=2) + "\n")
    shutil.rmtree(Path(__file__).resolve().parent / "__pycache__", ignore_errors=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
