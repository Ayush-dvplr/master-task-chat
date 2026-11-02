#!/bin/bash
set -u
export OPENAI_API_KEY=unused
ROOT='/Users/mac/Desktop/Terminal Bench/_runs/20261031/stage2-calib/replay-3d517b2'
WORK='/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1'
GUARD='/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py'
poll=10
until grep -q DONE "$ROOT/runs-public.log"; do
  for i in $(seq 20); do grep -q DONE "$ROOT/runs-public.log" && break; sleep 10; done
  poll=$((poll+1)); echo "poll $poll"; tail -5 "$ROOT/runs-public.log"
done
python3 "$WORK/scripts/tests_only.py" || exit 1
for task in royalty billing pm25; do
  for mode in oracle replay; do
    until python3 "$GUARD" --need-mb 4096 --cpus 2; do
      for i in $(seq 20); do python3 "$GUARD" --need-mb 4096 --cpus 2 >/dev/null && break; sleep 10; done
      poll=$((poll+1)); echo "poll $poll"
    done
    yes | harbor run -p "$ROOT/$task-$mode" --agent oracle -o "$ROOT/jobs" --env docker -y --job-name "a3-$task-$mode" -n 1 >"$ROOT/$task-$mode-tests-only.log" 2>&1
    echo "$task-$mode EXIT=$?"
  done
done
echo DONE
