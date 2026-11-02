#!/bin/bash
# usage: lanes.sh <stream-name> lane:copy:agent ...
export OPENAI_API_KEY=unused PYTHONDONTWRITEBYTECODE=1
L="/Users/mac/Desktop/Terminal Bench/_runs/20261102/slipway-overhaul-replan-repair/fix3-20261102T1448/lanes"
cd "$L/jobs"
S=$1; shift
for spec in "$@"; do
  IFS=: read name copy agent <<< "$spec"
  for i in $(seq 1 90); do
    python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 8192 --cpus 4 | tail -1 | sed "s/^/$name /" | tee -a "$L/logs/dockfree.log" | grep -q START=yes && break
    sleep 20
  done
  echo "$name start $(date +%T)"
  yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "$L/copies/$copy" --agent $agent --env docker --job-name $name --jobs-dir "$L/jobs" -y > "$L/logs/$name.log" 2>&1
  echo "$name rc $? $(date +%T)"
done
echo ALL_DONE
