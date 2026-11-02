"""Score one solver with method (b): run it, then the REAL tests/test_output.py under rewardkit 0.2.1.

    python3 harness.py ID SOLVER_PY|nop|stub
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

S = Path("/tmp/smpr-hard-20261021T1730")
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair")
PY312 = str(Path.home() / ".local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12")
ARTIFACTS = ["patched-repo.zip", "repair-report.json", "module_core.json", "module_parser.json",
             "module_report.json", "test_fixes.json", "summary.json"]


def main() -> None:
    ident, solver = sys.argv[1], sys.argv[2]
    app = S / "apps" / ident
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(BUNDLE / "environment" / "data", app / "data")
    env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
    started = time.time()
    if solver == "nop":
        solve_rc = 0
    elif solver == "stub":
        for name in ARTIFACTS:
            (app / "out" / name).write_text("" if name.endswith(".zip") else "{}", encoding="utf-8")
        solve_rc = 0
    elif solver == "stub_default":
        shutil.copyfile(app / "data" / "repo.zip", app / "out" / "patched-repo.zip")
        shapes = {
            "repair-report.json": {"package": "migrakit", "fixes": [], "checks": []},
            "module_core.json": {"module": "core", "changed_functions": [], "notes": []},
            "module_parser.json": {"module": "parser", "changed_functions": [], "notes": []},
            "module_report.json": {"module": "report", "changed_functions": [], "notes": []},
            "test_fixes.json": {"visible_tests": []},
            "summary.json": {"records": 0, "attempted": 0, "by_status": {}, "by_code": {}, "by_category": {},
                             "invalid_corrections": [], "partners": []},
        }
        for name, shape in shapes.items():
            (app / "out" / name).write_text(json.dumps(shape), encoding="utf-8")
        solve_rc = 0
    else:
        done = subprocess.run([PY312, solver], env=env, capture_output=True, text=True)
        (app / "solve.log").write_text(done.stdout + done.stderr, encoding="utf-8")
        solve_rc = done.returncode
    solve_sec = time.time() - started
    started = time.time()
    out = app / "reward.json"
    done = subprocess.run(
        ["uvx", "--python", "3.12", "--from", "harbor-rewardkit==0.2.1", "rewardkit", str(S / "tests_ql"),
         "--workspace", str(app), "--output", str(out)],
        env=env, capture_output=True, text=True)
    (app / "verifier.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    result = {"id": ident, "solver": solver, "solve_rc": solve_rc, "solve_sec": round(solve_sec, 1),
              "verify_rc": done.returncode, "verify_sec": round(time.time() - started, 1)}
    if out.exists():
        result["reward"] = json.loads(out.read_text())
    details = out.with_name("reward-details.json")
    if details.exists():
        result["details"] = json.loads(details.read_text())
    (S / "results").mkdir(exist_ok=True)
    (S / "results" / f"{ident}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}))


if __name__ == "__main__":
    main()
