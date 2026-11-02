#!/bin/bash
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_survey.py
chmod 0644 /app/out/derive_survey.py
python3 /app/out/derive_survey.py /app/data /app/out
