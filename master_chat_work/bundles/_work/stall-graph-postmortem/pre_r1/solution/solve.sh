#!/bin/bash
set -euo pipefail
SOLUTION_ROOT="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp "${SOLUTION_ROOT}/solve.py" /app/out/derive_report.py
chmod +x /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
# Instruction R4 requires the derivation to run again from an empty output
# directory once the constants are settled and produce byte-identical results.
# This block reproduces that check inside the oracle so drift is caught here.
SECOND_RUN="$(mktemp -d)"
python3 /app/out/derive_report.py /app/data "${SECOND_RUN}"
for report in "${SECOND_RUN}"/*.json; do
  cmp -s "${report}" "/app/out/$(basename "${report}")" || exit 1
done
rm -rf "${SECOND_RUN}"
