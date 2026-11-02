#!/bin/bash
# Re-score lane: the a3 program delivered and run over the shipped papers.
set -euo pipefail
S="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out /app/project
cp "$S/a3_engine.zip" /app/out/patched_engine.zip
cd /app/project && python3 -c "import zipfile; zipfile.ZipFile('/app/out/patched_engine.zip').extractall('/app/project')"
PYTHONPATH=/app/project/src PYTHONDONTWRITEBYTECODE=1 python3 -m slwopt --data /app/data --out /app/out
ls /app/out
