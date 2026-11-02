#!/bin/bash
# Oracle dispatcher for emberforge-vault-settlement.
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/settle_vault.py
python3 /app/out/settle_vault.py /app/data /app/out
