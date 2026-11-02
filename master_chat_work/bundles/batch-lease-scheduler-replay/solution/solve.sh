#!/bin/bash
# Repair the package, ship /app/out/package.zip and replay the shipped book.
set -euo pipefail

python3 /solution/solve.py

for name in package.zip selftest.json build_report.json module_core.json \
            module_metrics.json dependency_resolution.json summary.json; do
    if [ ! -s "/app/out/$name" ]; then
        echo "missing /app/out/$name" >&2
        exit 1
    fi
done
echo "wrote seven files under /app/out"
