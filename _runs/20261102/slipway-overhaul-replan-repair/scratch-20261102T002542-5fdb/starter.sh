#!/bin/bash
S="/Users/mac/Desktop/Terminal Bench/_runs/20261102/slipway-overhaul-replan-repair/scratch-20261102T002542-5fdb"
R="/Users/mac/Desktop/Terminal Bench/_runs/20261102/slipway-overhaul-replan-repair/qc-20261102T002542-5fdb"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
for k in 1 2 3; do
  until out=$(python3 "$DF" --need-mb 8192 --cpus 4) && echo "$out" | grep -q START=yes; do sleep 10; done
  echo "$(date +%H:%M:%S) lane $k START=yes: $out"
  nohup bash "$S/lane.sh" $k > "$R/logs/lane$k.log" 2>&1 &
  sleep 240
done
echo "$(date +%H:%M:%S) STARTER_DONE"
