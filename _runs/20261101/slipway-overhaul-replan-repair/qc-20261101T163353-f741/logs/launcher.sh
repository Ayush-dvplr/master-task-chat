#!/bin/bash
Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/qc-20261101T163353-f741"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
J="$Q/jobs"; L="$Q/logs"
RUN="$Q/copies/run/slipway-overhaul-replan-repair"; STUB="$Q/copies/stub/slipway-overhaul-replan-repair"; OWN="$Q/copies/owner/slipway-overhaul-replan-repair"
wait_free(){ n=0; until python3 "$DF" --need-mb 8192 --cpus 4 >/dev/null; do n=$((n+1)); sleep 15; done; echo "$(date +%T) free after $n waits $1"; }
cd /tmp
wait_free lane1
nohup bash -c "cd /tmp; for k in 1 2 3; do harbor run -p \"$RUN\" -a oracle -e docker -o \"$J\" -y --job-name oracle-\$k; echo EXIT oracle-\$k \$?; done; echo LANE_DONE" > "$L/lane1.log" 2>&1 &
echo "$(date +%T) lane1 launched"
sleep 120; wait_free lane2
nohup bash -c "cd /tmp; harbor run -p \"$OWN\" -a oracle -e docker -o \"$J\" -y --job-name owner-1; echo EXIT owner-1 \$?; echo LANE_DONE" > "$L/lane2.log" 2>&1 &
echo "$(date +%T) lane2 launched"
sleep 120; wait_free lane3
nohup bash -c "cd /tmp; harbor run -p \"$RUN\" -a nop -e docker -o \"$J\" -y --job-name nop-1; echo EXIT nop-1 \$?; harbor run -p \"$STUB\" -a oracle -e docker -o \"$J\" -y --job-name stub-1; echo EXIT stub-1 \$?; echo LANE_DONE" > "$L/lane3.log" 2>&1 &
echo "$(date +%T) lane3 launched"
echo LAUNCHER_DONE
