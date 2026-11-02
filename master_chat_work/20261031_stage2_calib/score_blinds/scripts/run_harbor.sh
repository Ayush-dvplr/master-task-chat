#!/bin/bash
set -euo pipefail
BASE='/Users/mac/Desktop/Terminal Bench'
WORK="$BASE/master_chat_work/20261031_stage2_calib/score_blinds"
SCRATCH="$BASE/_runs/20261031/stage2-calib/score-b366e00"
export OPENAI_API_KEY=unused
export PATH="/Users/mac/.local/bin:$PATH"
poll=0
for task in billing pm25 pension; do
  for kind in blind oracle; do
    while true; do
      gate=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2)
      printf '%s\n' "$gate"
      [[ "$gate" == *'START=yes'* ]] && break
      for i in $(seq 20); do python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done
      poll=$((poll+1)); echo "poll $poll"
    done
    name="b366e00-$task-$kind"
    echo "START $name"
    yes | harbor run -p "$SCRATCH/$task-$kind" --agent oracle -o "$SCRATCH/jobs" --env docker -y --job-name "$name" -n 1 || { rc=$?; [[ $rc == 141 ]] || exit "$rc"; }
    echo "FINISHED $name"
  done
done
echo DONE
