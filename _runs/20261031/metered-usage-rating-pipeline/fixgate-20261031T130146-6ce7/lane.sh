#!/bin/zsh
# usage: lane.sh <copydir> <agent> <job-name>...
R="${0:A:h}"; COPY="$1"; AGENT="$2"; shift 2
for J in "$@"; do
  echo "$(date +%H:%M:%S) start $J"
  harbor run --path "$COPY" --agent "$AGENT" --env docker --job-name "$J" --jobs-dir "$R/jobs" -y
  echo "$(date +%H:%M:%S) end $J rc=$?"
done
echo LANE_DONE
echo ALL_DONE
