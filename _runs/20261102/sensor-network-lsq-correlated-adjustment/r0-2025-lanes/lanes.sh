#!/bin/bash
export OPENAI_API_KEY=unused PYTHONDONTWRITEBYTECODE=1
L="/Users/mac/Desktop/Terminal Bench/_runs/20261102/sensor-network-lsq-correlated-adjustment/r0-2025-lanes"
cd "$L/jobs"
for spec in "$@"; do
  IFS=: read name copy agent <<< "$spec"
  for i in $(seq 1 90); do
    python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 | tail -1 | sed "s/^/$name /" | tee -a "$L/logs/dockfree.log" | grep -q START=yes && break
    sleep 20
  done
  echo "$name start $(date +%T)"
  yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "$L/copies/$copy" --agent $agent --env docker --job-name $name --jobs-dir "$L/jobs" -y > "$L/logs/$name.log" 2>&1
  echo "$name rc $? $(date +%T)"
done
echo ALL_DONE
