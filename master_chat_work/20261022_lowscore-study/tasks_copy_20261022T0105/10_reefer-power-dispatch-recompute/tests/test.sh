#!/bin/bash
set -euo pipefail

rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/reward-details.json
mkdir -p /logs/verifier
chown root:root /logs/verifier
chmod 700 /logs/verifier
chmod -R go-rwx /tests

exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json
