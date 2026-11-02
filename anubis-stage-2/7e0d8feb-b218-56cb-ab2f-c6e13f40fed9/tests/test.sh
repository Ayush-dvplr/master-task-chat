#!/bin/bash
set -euo pipefail

# Stale rewards are cleared first, so a score left by an earlier run can never
# be collected as this one's.
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/reward-details.json
mkdir -p /logs/verifier

# The reward directory belongs to root and stays shut for the whole grading
# window, so nothing the delivered program spawns can drop a score into it.
chown root:root /logs/verifier
chmod 755 /logs/verifier

# The grading machinery stays unreadable to everything but root, so a
# submission cannot read the criteria it is about to be measured against.
chmod -R go-rwx /tests

exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json
