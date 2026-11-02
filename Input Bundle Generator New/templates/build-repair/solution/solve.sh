#!/bin/bash
# Oracle dispatcher for {{BUNDLE_NAME}}.
set -euo pipefail

python3 /solution/solve.py

PYTHONPATH=/app/project/src python3 -m unittest discover -s /app/project/tests -v

python3 - <<'PY'
import importlib.util
import sys
from pathlib import Path

project = Path("/app/project")
sys.path.insert(0, str(project / "src"))
pkg = importlib.import_module("{{PACKAGE_NAME}}")
entries = [
    {"name": "oracle-a", "expected": 100, "observed": 100, "seconds": 1},
    {"name": "oracle-b", "expected": 100, "observed": 126, "seconds": 42, "critical": True},
]
summary = pkg.summarize(entries)
if summary["count"] != 2 or summary["items"][0]["bucket"] != "ok":
    raise SystemExit("oracle API smoke check failed")
out = Path("/app/out")
required = [
    "package.zip",
    "selftest.json",
    "build_report.json",
    "module_core.json",
    "module_metrics.json",
    "dependency_resolution.json",
    "summary.json",
]
missing = [name for name in required if not (out / name).is_file()]
if missing:
    raise SystemExit(f"missing oracle artifacts: {missing}")
PY

echo "[oracle] repaired {{PACKAGE_NAME}} and wrote seven artifacts under /app/out"
