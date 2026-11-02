#!/bin/bash
# Score-only: installs the blind solution's delivered files byte for byte. No program is run.
set -euo pipefail
S="${SOLUTION_ROOT:-/solution}"
mkdir -p /app/out
cp -R "$S/blind_app/." /app/
cp -R "$S/blind_out/." /app/out/
echo "INSTALLED_SHA256_BEGIN"
cd "$S/blind_app" && find . -type f | sort | while read -r f; do sha256sum "/app/${f#./}"; done
cd "$S/blind_out" && find . -type f | sort | while read -r f; do sha256sum "/app/out/${f#./}"; done
echo "INSTALLED_SHA256_END"
