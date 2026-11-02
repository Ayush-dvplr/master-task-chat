#!/usr/bin/env python3
"""Author-side tests-channel replay with a minimal rewardkit registration stub."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BUNDLE = ROOT.parents[1] / "dispatch-plan-reoptimization"
NAMES = ["oracle", "agent_v0", "m_fallback", "m_tie", "m_amend", "m_rejnorm", "m_voidlog"]


def variants():
    src = (BUILD / "oracle.py").read_text()
    # The verifier image uses newer Python; this host's Path.write_text lacks newline.
    # On this Unix host omitting newline has the same LF bytes.
    src = src.replace(', encoding="utf-8", newline="\\n")', ', encoding="utf-8")')
    dest = ROOT / "trap/variants"
    dest.mkdir(exist_ok=True)
    (dest / "oracle.py").write_text(src)
    replacements = {
        "m_fallback": [('st["fallback"].get(it, st["default_setup"])', 'st["default_setup"]')],
        "m_tie": [('if best[b] is None or cand < best[b]:', 'if best[b] is None or cand <= best[b]:')],
        "m_amend": [
            ('        if to_int(get(row, "void") or 0) == 1:\n            marks.setdefault(key, set()).add("VOI")\n            continue',
             '        ident = idfn(row) if idfn else (key, row["__src"], row["__idx"])\n        if ident in seen:\n            continue\n        seen.add(ident)\n        if to_int(get(row, "void") or 0) == 1:\n            marks.setdefault(key, set()).add("VOI")\n            continue'),
            ('        ident = idfn(row) if idfn else (key, row["__src"], row["__idx"])\n        if ident in seen:\n            continue\n        seen.add(ident)\n        sign = signfn(row)', '        sign = signfn(row)'),
        ],
        "m_rejnorm": [('if demand_like:\n                code = norm_code(get(row, "item_code", "item", "sku", "code"))',
                         'if demand_like:\n                code = str(get(row, "item_code", "item", "sku", "code"))')],
        "m_voidlog": [('elif to_int(get(row, "void") or 0) == 1 or ctx.lifecycle.get(uid):',
                        'elif to_int(get(row, "void") or 0) == 1:')],
    }
    for name, repls in replacements.items():
        text = src
        for old, new in repls:
            count = text.count(old)
            if count != 1:
                raise RuntimeError(f"{name} replacement found {count}: {old[:50]}")
            text = text.replace(old, new)
        (dest / f"{name}.py").write_text(text)
    return dest


class Registry:
    def __init__(self):
        self.weights = {}

    def __getattr__(self, name):
        def register(weight):
            self.weights[name] = weight
        return register


def score(test_file, name, program, data):
    with tempfile.TemporaryDirectory(prefix="dpr-grade-") as tmp:
        tmp = Path(tmp)
        app = tmp / "app"
        out = app / "out"
        out.mkdir(parents=True)
        target = out / "solver.py"
        shutil.copy2(program, target)
        run = subprocess.run([sys.executable, str(target), str(data), str(out)],
                             cwd=tmp, capture_output=True, text=True, timeout=400)
        if run.returncode:
            return dict(name=name, valid=False, stderr=run.stderr[-1000:])
        reg = Registry()
        fake = types.ModuleType("rewardkit")
        fake.criteria = reg
        fake.criterion = lambda **kw: lambda f: f
        sys.modules["rewardkit"] = fake
        os.environ["APP_ROOT"] = str(app)
        spec = importlib.util.spec_from_file_location("grade_target", test_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        got = {}
        for check, weight in reg.weights.items():
            try:
                got[check] = bool(getattr(mod, check)(app))
            except Exception as exc:
                return dict(name=name, valid=False, error=f"{check}: {exc!r}")
        pos = sum(w for check, w in reg.weights.items() if w > 0)
        earned = sum(w for check, w in reg.weights.items() if w > 0 and got[check])
        penalty = sum(w for check, w in reg.weights.items() if w < 0 and got[check])
        return dict(name=name, valid=True, positive=pos, earned=earned,
                    penalty=penalty, score=max(0, earned+penalty)/pos,
                    failed=[k for k, w in reg.weights.items() if w > 0 and not got[k]],
                    triggered=[k for k, w in reg.weights.items() if w < 0 and got[k]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tests")
    ap.add_argument("environment")
    ap.add_argument("output")
    args = ap.parse_args()
    dest = variants()
    programs = {"oracle": dest / "oracle.py", "agent_v0": BUILD / "agent_v0.py"}
    programs.update({name: dest / f"{name}.py" for name in NAMES[2:]})
    data = Path(args.environment).resolve() / "data"
    results = [score(Path(args.tests).resolve(), name, programs[name], data) for name in NAMES]
    Path(args.output).write_text(json.dumps(results, indent=2) + "\n")
    for r in results:
        print(r['name'], r.get('score'), r.get('valid'), r.get('earned'), r.get('penalty'))


if __name__ == "__main__":
    main()
