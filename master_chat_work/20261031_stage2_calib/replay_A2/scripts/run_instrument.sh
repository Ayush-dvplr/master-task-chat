#!/bin/bash
set -euo pipefail
BASE='/Users/mac/Desktop/Terminal Bench'
WORK="$BASE/master_chat_work/20261031_stage2_calib/replay_A2"
SCRATCH="$BASE/_runs/20261031/stage2-calib/replay-4e9d595"
for task in pension spectrum; do
  gate=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2)
  printf '%s\n' "$gate"
  [[ "$gate" == *'START=yes'* ]] || exit 2
  docker build -t "a2-$task-verifier:local" "$SCRATCH/$task-oracle/tests"
  gate=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2)
  printf '%s\n' "$gate"
  [[ "$gate" == *'START=yes'* ]] || exit 2
  docker run --rm --name "a2-$task-instrument" --cpus 2 --memory 4g \
    -v "$WORK:/evidence" -v "$WORK/scripts:/driver:ro" \
    -v "$SCRATCH/$task-oracle/solution:/oracle:ro" \
    -v "$SCRATCH/$task-replay/solution/captured-app:/captured:ro" \
    "a2-$task-verifier:local" python /driver/instrument.py "$task"
done
printf 'DONE\n'
