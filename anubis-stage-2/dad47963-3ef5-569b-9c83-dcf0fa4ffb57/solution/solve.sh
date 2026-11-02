#!/bin/bash
# Oracle for dad47963-3ef5-569b-9c83-dcf0fa4ffb57: install the reference engine and run it on the shipped estate.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/monitor.py
python3 /app/out/monitor.py /app/data /app/out
