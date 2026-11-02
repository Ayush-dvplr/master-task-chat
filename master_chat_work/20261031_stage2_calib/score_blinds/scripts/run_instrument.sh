#!/bin/bash
set -euo pipefail
BASE='/Users/mac/Desktop/Terminal Bench'
W="$BASE/master_chat_work/20261031_stage2_calib/score_blinds"
S="$BASE/_runs/20261031/stage2-calib/score-b366e00"
poll=0
while ! grep -q '^DONE$' "$W/harbor.log"; do
  for i in $(seq 20); do grep -q '^DONE$' "$W/harbor.log" && break; sleep 10; done
  poll=$((poll+1)); echo "poll $poll"; tail -5 "$W/harbor.log"
done
for task in billing pm25 pension; do
  for subject in blind opus; do
    while true; do
      gate=$(python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2)
      printf '%s\n' "$gate"
      [[ "$gate" == *'START=yes'* ]] && break
      for i in $(seq 20); do python3 "$BASE/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done
      poll=$((poll+1)); echo "poll $poll"
    done
    script=instrument_clocks.py
    [[ "$task" == pension ]] && script=reused_A2_instrument.py
    captured="$S/$task-$subject-app"
    mkdir -p "$W/$subject-evidence"
    echo "START $task $subject"
    docker run --rm --name "b366e00-$task-$subject-instrument" --network none --cpus 2 --memory 4g --user root \
      -v "$W/scripts:/instrument:ro" -v "$captured:/captured:ro" \
      -v "$S/$task-oracle/tests:/input-tests:ro" -v "$S/$task-oracle/solution:/oracle:ro" \
      -v "$W/$subject-evidence:/evidence" b366e00-instrument:local \
      bash -c 'rm -rf /tests; cp -a /input-tests /tests; chmod 700 /tests; python3 /instrument/'"$script"' '"$task"
    echo "FINISHED $task $subject"
  done
done
echo DONE
