"""G5 vacuity probe: score the unedited shipped package with every check.

usage: python3 -B vacuity_p12.py OUT_JSON
Variants:
  nothing    no file under /app/out (an agent who did nothing)
  unedited   the shipped repo, untouched, zipped per build_config, plus the
             oracle-shaped report files computed from the untouched package
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
MAIN_OLD = "    repair_sources()\n    visible_ok = run_visible_tests()\n    if not visible_ok:\n        raise SystemExit(\"visible tests fail after repair\")\n"
MAIN_NEW = "    visible_ok = run_visible_tests()\n"
CHECK_OLD = "        self_check(tariff, cases, rows, scratch)\n"
REPLAY_OLD = "        cases, rows = replay_cases(tariff, scratch)\n"
REPLAY_NEW = ("        try:\n            cases, rows = replay_cases(tariff, scratch)\n"
              "        except Exception:\n            cases, rows = [], []\n")
DET_OLD = "        deterministic = tariff.build_invoices(CI) == tariff.build_invoices(CI)\n"
DET_NEW = ("        try:\n            deterministic = tariff.build_invoices(CI) == tariff.build_invoices(CI)\n"
           "        except Exception:\n            deterministic = False\n")


def run(name):
    root = Path(tempfile.mkdtemp(prefix="vacuity-"))
    app = root / "app"
    shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
    shutil.copytree(BUNDLE / "environment" / "repo", app / "repo")
    env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
    if name == "unedited":
        text = (BUNDLE / "solution" / "solve.py").read_text(encoding="utf-8")
        for old, new in ((MAIN_OLD, MAIN_NEW), (CHECK_OLD, ""), (REPLAY_OLD, REPLAY_NEW), (DET_OLD, DET_NEW)):
            assert text.count(old) == 1, old
            text = text.replace(old, new)
        (root / "solve.py").write_text(text, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(root / "solve.py")], env=env, capture_output=True, text=True)
        if proc.returncode:
            return {"error": proc.stderr[-800:]}
    out = root / "checks.json"
    subprocess.run([sys.executable, "-B", str(WORK / "run_checks.py"), str(app), str(out)], env=env,
                   capture_output=True, text=True, check=True)
    result = json.loads(out.read_text())
    shutil.rmtree(root, ignore_errors=True)
    return result


def main():
    target = Path(sys.argv[1])
    results = {}
    for name in ("nothing", "unedited"):
        result = run(name)
        results[name] = result
        passed = [k for k, v in result.get("checks", {}).items() if v["pass"] and v["weight"] > 0]
        print(name, result.get("earned"), "/", result.get("positive"), "positive passes:", passed, result.get("error", ""), flush=True)
        target.write_text(json.dumps(results, indent=1))
    print("ALL_DONE")


if __name__ == "__main__":
    main()
