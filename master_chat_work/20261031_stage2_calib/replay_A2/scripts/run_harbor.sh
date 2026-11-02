#!/bin/bash
set -u
BASE='/Users/mac/Desktop/Terminal Bench'
SCRATCH="$BASE/_runs/20261031/stage2-calib/replay-4e9d595"
export OPENAI_API_KEY=unused
export PATH="/Users/mac/.local/bin:$PATH"
for task in pension-oracle pension-replay spectrum-oracle spectrum-replay; do
  while true; do
    gate=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2)
    printf '%s\n' "$gate"
    if [[ "$gate" == *'START=yes'* ]]; then break; fi
    sleep 10
  done
  yes | harbor run -p "$SCRATCH/$task" --agent oracle -o "$SCRATCH/jobs" --env docker -y --job-name "a2-local-$task" -n 1
  printf 'FINISHED %s status=%s\n' "$task" "$?"
done
printf 'DONE\n'
