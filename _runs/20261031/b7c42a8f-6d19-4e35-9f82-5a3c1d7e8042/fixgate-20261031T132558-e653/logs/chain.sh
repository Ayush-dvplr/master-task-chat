#!/bin/bash
R="/Users/mac/Desktop/Terminal Bench/_runs/20261031/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/fixgate-20261031T132558-e653"
cd "$R/copies/plain/tests" && docker build --progress plain -t warm-b7c-v5 . > "$R/logs/warm.log" 2>&1; echo WARM_EXIT=$?
cd "$R/copies/plain/environment" && docker build --progress plain -t warm-b7c-v5env . >> "$R/logs/warm.log" 2>&1; echo WARMENV_EXIT=$?
waitfree() { for i in $(seq 90); do python3 '/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py' --need-mb 4096 --cpus 2 | grep -q START=yes && return 0; sleep 20; done; echo DOCKFREE_TIMEOUT; }
run() { cd /tmp; harbor run --path "$R/copies/$1" --agent $2 --env docker -y --no-delete -o "$R/jobs" --job-name b7cdbe-$3-20261031T132558-e653; echo EXIT_$3=$?; }
waitfree; ( for n in 1 2 3; do run plain oracle oracle$n; done; echo LANE_DONE ) > "$R/logs/lane1.log" 2>&1 &
sleep 30; waitfree; ( run owner oracle owner1; echo LANE_DONE ) > "$R/logs/lane2.log" 2>&1 &
sleep 30; waitfree; ( run plain nop nop1; echo LANE_DONE ) > "$R/logs/lane3.log" 2>&1 &
wait
echo ALL_DONE
