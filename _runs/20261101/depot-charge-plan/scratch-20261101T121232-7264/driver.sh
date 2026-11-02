#!/bin/zsh
R="/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/qc-20261101T121232-7264"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
export J="$R/jobs" L="$R/logs" C="$R/copies"
waitfree() { n=30; until python3 "$DF" --need-mb 4096 --cpus 2 >> "$L/dockfree.log" 2>&1; do echo "$(date +%T) wait $1 ${n}s" >> "$L/runs.log"; sleep $n; [ $n -lt 180 ] && n=$((n+30)); done; echo "$(date +%T) start $1" >> "$L/runs.log"; }
lane1() { for i in 1 2 3; do harbor run --path "$C/run/depot-charge-plan" --agent oracle --env docker -o "$J" --job-name oracle-$i -y; echo "oracle-$i rc=$?"; done; echo LANE_DONE; }
lane2() { harbor run --path "$C/owner/depot-charge-plan" --agent oracle --env docker -o "$J" --job-name owner-only-1 -y; echo "owner rc=$?"; echo LANE_DONE; }
lane3() { harbor run --path "$C/run/depot-charge-plan" --agent nop --env docker -o "$J" --job-name nop-1 -y; echo "nop rc=$?"; harbor run --path "$C/stub/depot-charge-plan" --agent oracle --env docker -o "$J" --job-name stub-1 -y; echo "stub rc=$?"; echo LANE_DONE; }
waitfree lane1; nohup zsh -c "$(functions lane1); lane1" > "$L/lane1.log" 2>&1 & p1=$!; sleep 90
waitfree lane2; nohup zsh -c "$(functions lane2); lane2" > "$L/lane2.log" 2>&1 & p2=$!; sleep 90
waitfree lane3; nohup zsh -c "$(functions lane3); lane3" > "$L/lane3.log" 2>&1 & p3=$!
wait $p1 $p2 $p3
echo ALL_DONE >> "$L/runs.log"
rmdir /tmp/opencode-logs/locks/depot-charge-plan.lock
