#!/bin/bash
set -eu
R='/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
W='/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio/fix4'
B='/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio'
if grep -q '^ALL_DONE$' "$R/logs/live-cheat.log" 2>/dev/null; then exit 0; fi
while true; do
  python3 '/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py' --need-mb 4096 --cpus 2 > "$R/logs/free-live-cheat.log"
  if grep -q 'START=yes' "$R/logs/free-live-cheat.log"; then break; fi
  sleep 20
done
perl -e 'alarm 900; exec @ARGV' docker run --rm --pull never --memory 4g --cpus 2 --network none --name 420bf9a-live-cheat -v "$B:/bundle:ro" -v "$W:/probes:ro" python:3.12-slim python3 -B /probes/live_cheat_probe.py > "$R/logs/live-cheat.log" 2>&1
echo ALL_DONE
