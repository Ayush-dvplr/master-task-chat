"""Score a mutated oracle: repair the shipped tool with solve.py, apply extra edits, deliver, run every check."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "data-product-config-compiler"
SCRATCH = Path(os.environ.get("DPCC_SCRATCH", "/tmp/dpcc-P4-20261024T2014"))
RUNALL = SCRATCH / "rk" / "runall.py"

DRIVER = r'''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("solve", sys.argv[1])
solve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solve)
solve.EDITS.extend(tuple(edit) for edit in json.loads(sys.argv[2]))
solve.repair_tool()
try:
    solve.deliver()
except AssertionError as error:
    print("deliver failed:", str(error)[-300:])
    import zipfile
    solve.OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(solve.OUT / "tool.zip", "w") as archive:
        for name in solve.SOURCES:
            archive.write(solve.TOOL / name, name)
'''


def score(label: str, edits: list[tuple[str, str, str]], solve_edits: list[tuple[str, str]] = ()) -> dict:
    app = SCRATCH / "runs" / label / "app"
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(BUNDLE / "environment" / "data", app / "data")
    solver = BUNDLE / "solution" / "solve.py"
    if solve_edits:
        text = solver.read_text()
        for old, new in solve_edits:
            assert text.count(old) == 1, (label, old)
            text = text.replace(old, new)
        solver = app.parent / "solve_mutant.py"
        solver.write_text(text)
    env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
    prep = subprocess.run([sys.executable, "-B", "-c", DRIVER, str(solver), json.dumps(edits)],
                          env=env, capture_output=True, text=True, cwd=str(SCRATCH))
    assert prep.returncode == 0, (label, prep.stderr[-800:])
    done = subprocess.run([sys.executable, "-B", str(RUNALL), str(BUNDLE / "tests" / "test_output.py")],
                          env=env, capture_output=True, text=True, cwd=str(SCRATCH))
    assert done.returncode == 0, (label, done.stderr[-800:])
    result = json.loads(done.stdout.strip().splitlines()[-1])
    result["label"] = label
    result["got"], result["pos"] = max(0, result["earned"]), result["total"]
    result["pct"] = round(100 * result["got"] / result["pos"], 1)
    result["failed"] = [name for name, (weight, ok, _) in result["rows"].items() if weight > 0 and not ok]
    result["deliver"] = prep.stdout.strip()
    return result


# Wrong readings, written as edits on the repaired tool.
L1_FULL = [("resolve.py", '        if retired_owners.get(product["owner"], "9999-99-99") <= day:\n            owner_now = None\n', "")]
L1_ONE = [("resolve.py", '        if retired_owners.get(product["owner"], "9999-99-99") <= day:\n',
           '        first = min((o for o, d in retired_owners.items() if d <= day\n'
           '                     and any(p["owner"] == o for p in products.values())), default="")\n'
           '        if retired_owners.get(product["owner"], "9999-99-99") <= day and product["owner"] != first:\n')]
L2_FULL = [("resolve.py", '    if not json_type_ok(spec, value):\n        return "type", None\n',
            '    try:\n        from loaders import coerce\n        value = coerce(spec, value)\n'
            '    except ValueError:\n        return "type", None\n')]
L2_ONE = [("resolve.py", '    if not json_type_ok(spec, value):\n',
           '    if isinstance(value, str) and spec.get("max") == 3650 and value.strip().isdigit():\n'
           '        value = int(value)\n'
           '    if not json_type_ok(spec, value):\n')]
L4_FULL = [("loaders.py", '            pid = canon(fields["product"])\n', '            pid = fields["product"]\n')]
L4_ONE = [("loaders.py", '            pid = canon(fields["product"])\n', '            pid = fields["product"].upper()\n')]
BACKGROUND = {"LV-CC-1": (L1_FULL, L1_ONE), "LV-CC-2": (L2_FULL, L2_ONE), "LV-CC-4": (L4_FULL, L4_ONE)}

N1_FULL = [("resolve.py",
            '    latest = None\n    for row in owner_rows:\n        if row["owner"] == owner and row["active_from"] <= day:\n'
            '            if latest is None or row["active_from"] > latest["active_from"]:\n                latest = row\n'
            '    if latest is None or (latest["active_to"] != "" and latest["active_to"] < day):\n        return None\n'
            '    return latest["team"]\n',
            '    for row in owner_rows:\n        if row["owner"] == owner and row["active_from"] <= day and (\n'
            '                row["active_to"] == "" or row["active_to"] >= day):\n            return row["team"]\n    return None\n')]
N1_ONE = [("resolve.py", '        if row["owner"] == owner and row["active_from"] <= day:\n',
           '        if row["owner"] == owner and row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day):\n')]
N4_FULL = [("loaders.py", '        if not text or any(char not in "0123456789" for char in text):\n            raise ValueError(value)\n', ''),
           ("loaders.py", '        if text not in ("true", "false"):\n            raise ValueError(value)\n', '')]
N4_ONE = [("loaders.py", '        if not text or any(char not in "0123456789" for char in text):\n', '        if not text.isdigit():\n')]
N3_FULL = [("quota.py",
            '    held = {pid: 0 for pid in weights}\n    pool, taking = quota, dict(weights)\n',
            '    fixed = {}\n    while True:\n        free = {pid: w for pid, w in weights.items() if pid not in fixed}\n'
            '        held = dict(fixed)\n        held.update(split_quota(quota - sum(fixed.values()), free))\n'
            '        over = [pid for pid in free if caps.get(pid) is not None and held[pid] > caps[pid]]\n'
            '        if not over:\n            return held\n        for pid in over:\n            fixed[pid] = caps[pid]\n'
            '    held = {pid: 0 for pid in weights}\n    pool, taking = quota, dict(weights)\n')]
N3_ONE = [("quota.py", '    while pool > 0 and taking:\n', '    rounds = 0\n    while pool > 0 and taking and rounds < 2:\n        rounds += 1\n')]
LEVERS = {"NL-1": (N1_FULL, N1_ONE), "NL-3": (N3_FULL, N3_ONE), "NL-4": (N4_FULL, N4_ONE)}
