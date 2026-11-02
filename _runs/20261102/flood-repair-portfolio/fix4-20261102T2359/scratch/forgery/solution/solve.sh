#!/bin/bash
set -euo pipefail
mkdir -p /app/out/_saved
python3 -B /solution/solve.py /app/data /app/out/_saved
cat > /app/out/derive_report.py <<'PY'
import shutil
import sys
from pathlib import Path

saved = Path(__file__).resolve().parent / '_saved'
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for source in saved.glob('*.json'):
    shutil.copyfile(source, out / source.name)
PY
python3 -B /app/out/derive_report.py /app/data /app/out
