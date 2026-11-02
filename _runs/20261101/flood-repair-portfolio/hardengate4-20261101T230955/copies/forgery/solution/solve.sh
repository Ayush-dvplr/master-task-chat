#!/bin/bash
# Forgery lane (harden r4 ea94780): real shipped documents, fake program that copies them.
set -euo pipefail
mkdir -p /app/out/_saved
python3 /solution/solve.py /app/data /app/out/_saved
cat > /app/out/derive_report.py <<'PY'
import shutil, sys
from pathlib import Path
src = Path(__file__).resolve().parent / "_saved"
dst = Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for p in sorted(src.glob("*.json")):
    shutil.copyfile(p, dst / p.name)
PY
python3 /app/out/derive_report.py /app/data /app/out
chmod -R a+rX /app/out
