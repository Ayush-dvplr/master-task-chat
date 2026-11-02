"""Run a blind program (WORK/blind_rN/app) on the current BUNDLE data and score it with the real checks.

usage: python3 blind_measure.py blind_r2 OUT_JSON
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
name, target = sys.argv[1], Path(sys.argv[2])
root = Path(tempfile.mkdtemp(prefix=f"t3-{name}-"))
app = root / "app"
shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
shutil.copytree(WORK / name / "app" / "repo", app / "repo")
(app / "out").mkdir()
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", APP_ROOT=str(app))
ARGS = ["--repo", str(app / "repo"), "--ci", str(app / "ci"), "--out", str(app / "out")] if name == "blind_r1" else [str(app / "repo"), str(app / "ci"), str(app / "out")]
proc = subprocess.run([sys.executable, "-B", str(WORK / name / "app" / "build_deliverables.py"), *ARGS], env=env,
                      capture_output=True, text=True)
print("build rc", proc.returncode, proc.stderr[-400:])
subprocess.run([sys.executable, str(WORK / "run_checks.py"), str(app), str(target)], env=env, check=True,
               capture_output=True, text=True)
result = json.loads(target.read_text())
print(name, json.dumps(result.get("score", result))[:300])
failed = [k for k, v in result["checks"].items() if not v["pass"] and v["weight"] > 0]
print("failed", failed)
shutil.rmtree(root, ignore_errors=True)
