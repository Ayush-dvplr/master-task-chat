#!/bin/bash
set -euo pipefail
mkdir -p /app/out
cp -a /solution/blind-app/. /app/out/
python3 /app/out/transform.py /app/data /app/out
