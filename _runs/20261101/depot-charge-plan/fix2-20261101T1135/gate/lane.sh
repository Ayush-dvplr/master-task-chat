#!/bin/bash
# usage: lane.sh <lane-name> <copy:agent:job> ...
set -uo pipefail
R="/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/fix2-20261101T1135"
export OPENAI_API_KEY=unused
lane="$1"; shift
for spec in "$@"; do
  copy="${spec%%:*}"; rest="${spec#*:}"; agent="${rest%%:*}"; job="${rest#*:}"
  until python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | grep -q START=yes; do sleep 15; done
  echo "START $job $(date +%T)"
  yes | harbor run -p "$R/gate/$copy/depot-charge-plan" --agent "$agent" -o "$R/jobs" --env docker -y --job-name "$job" -n 1
  echo "HARBOR_EXIT $job=${PIPESTATUS[1]} $(date +%T)"
done
echo ALL_DONE
