#!/bin/bash
set -eu
W='/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio/fix4'
R='/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
for lane in oracle2 oracle3 owner; do
  if grep -q '^ALL_DONE$' "$R/logs/$lane.log" 2>/dev/null; then
    echo "SKIP completed $lane"
    continue
  fi
  copy=plain
  if [[ "$lane" == owner ]]; then copy=owner; fi
  while true; do
    if bash "$W/harbor_lane.sh" "$lane" "$R/scratch/$copy" oracle > "$R/logs/$lane.log" 2>&1; then
      break
    else
      rc=$?
      if [[ "$rc" != 3 ]]; then exit "$rc"; fi
      echo "$lane waiting for resource admission"
      sleep 20
    fi
  done
  echo "FINISHED $lane"
done
echo ALL_DONE
