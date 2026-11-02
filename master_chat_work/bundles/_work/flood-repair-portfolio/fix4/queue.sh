#!/bin/bash
set -euo pipefail
W='/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio/fix4'
R='/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
for lane in "$@"; do
  if grep -q '^ALL_DONE$' "$R/logs/$lane.log" 2>/dev/null; then echo "SKIP completed $lane"; continue; fi
  while true; do
    free=$(python3 '/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py' --need-mb 4096 --cpus 2) || true
    echo "$lane $free"
    if [[ "$free" == *START=yes* ]]; then break; fi
    sleep 20
  done
  copy=plain
  agent=oracle
  case "$lane" in owner|stub|forgery|paid) copy=$lane ;; nop) agent=nop ;; esac
  bash "$W/harbor_lane.sh" "$lane" "$R/scratch/$copy" "$agent" > "$R/logs/$lane.log" 2>&1
  echo "FINISHED $lane"
done
echo ALL_DONE
