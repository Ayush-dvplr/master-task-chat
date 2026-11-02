#!/bin/bash
set -euo pipefail

rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/reward-details.json
mkdir -p /logs/verifier
chown root:root /logs/verifier
chmod 755 /logs/verifier
chmod -R go-rwx /tests

python3 /tests/blind_instrument.driver spectral /logs/verifier/blind_instrument

exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json
