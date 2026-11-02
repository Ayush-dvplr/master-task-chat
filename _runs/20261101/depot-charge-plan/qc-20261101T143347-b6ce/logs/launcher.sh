#!/bin/bash
Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/qc-20261101T143347-b6ce"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
RUN="$Q/copies/run/depot-charge-plan"; STUB="$Q/copies/stub/depot-charge-plan"; OWNER="$Q/copies/owner/depot-charge-plan"; J="$Q/jobs"; L="$Q/logs"
while ! grep -q WARM_ENV_EXIT "$L/warm_env.log" 2>/dev/null; do sleep 10; done
echo "warm done $(date +%H:%M:%S)"
waitslot() { n=0; until python3 "$DF" --need-mb 4096 --cpus 2 >/dev/null; do n=$((n+1)); sleep 10; done; echo "slot for $1 after $n polls $(date +%H:%M:%S)"; python3 "$DF" --need-mb 4096 --cpus 2; }
waitslot lane1
nohup bash -c "cd /tmp; for k in 1 2 3; do harbor run -p \"$RUN\" --agent oracle -o \"$J\" --env docker -y --job-name oracle-\$k; echo RUN_EXIT oracle-\$k=\$?; done; echo LANE_DONE" > "$L/lane1.log" 2>&1 &
sleep 90
waitslot lane2
nohup bash -c "cd /tmp; harbor run -p \"$OWNER\" --agent oracle -o \"$J\" --env docker -y --job-name owner-1; echo RUN_EXIT owner-1=\$?; echo LANE_DONE" > "$L/lane2.log" 2>&1 &
sleep 90
waitslot lane3
nohup bash -c "cd /tmp; harbor run -p \"$RUN\" --agent nop -o \"$J\" --env docker -y --job-name nop-1; echo RUN_EXIT nop-1=\$?; harbor run -p \"$STUB\" --agent oracle -o \"$J\" --env docker -y --job-name stub-1; echo RUN_EXIT stub-1=\$?; echo LANE_DONE" > "$L/lane3.log" 2>&1 &
echo "all lanes launched $(date +%H:%M:%S)"
