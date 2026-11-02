#!/bin/bash
# Oracle dispatcher for {{BUNDLE_NAME}}.
set -euo pipefail

python3 /solution/solve.py

echo "[oracle] drove local service and wrote seven deterministic /app/out artifacts"
