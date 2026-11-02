#!/bin/bash
set -u
ROOT='/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2'
WORK='/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1'
GUARD='/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py'
poll=0
for task in royalty billing pm25; do
  until python3 "$GUARD" --need-mb 4096 --cpus 2; do
    for i in $(seq 20); do python3 "$GUARD" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done
    poll=$((poll+1)); echo "poll $poll"
  done
  docker build --progress plain -t "a1-verifier-$task" "$ROOT/$task-oracle/tests" >"$ROOT/$task-verifier-build.log" 2>&1 || continue
  until python3 "$GUARD" --need-mb 4096 --cpus 2; do
    for i in $(seq 20); do python3 "$GUARD" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done
    poll=$((poll+1)); echo "poll $poll"
  done
  docker run --rm --name "a1-diag-$task" --cpus 2 --memory 4096m --network none -v "$WORK/scripts:/drivers:ro" -v "$WORK/evidence/$task:/evidence" -v "$ROOT/$task-replay/solution/payload/out:/app/out:ro" -v "$ROOT/$task-oracle/solution:/oracle:ro" "a1-verifier-$task" python /drivers/diagnose.py "$task" >"$ROOT/$task-diagnostics.log" 2>&1
  echo "$task DIAGNOSTICS_EXIT=$?"
done
echo DONE
