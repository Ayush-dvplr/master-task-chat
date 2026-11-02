#!/bin/bash
# Vacuity lane: the shipped unrepaired engine delivered unchanged and run over the shipped papers.
set -euo pipefail
mkdir -p /app/out /app/project
cp /app/data/project.zip /app/out/patched_engine.zip
python3 -c "import zipfile; zipfile.ZipFile('/app/data/project.zip').extractall('/app/project')"
PYTHONPATH=/app/project/src PYTHONDONTWRITEBYTECODE=1 python3 -m slwopt --data /app/data --out /app/out || echo "shipped engine exited $?"
ls /app/out
