#!/bin/bash
export OPENAI_API_KEY=unused
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix1-1750/lanes"
cd "$L/jobs"
run() { # name copy agent
  for i in $(seq 1 60); do
    python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 8192 --cpus 4 | tail -1 | tee -a "$L/logs/dockfree.log" | grep -q START=yes && break
    sleep 20
  done
  echo "$1 start $(date +%T)"
  yes | perl -e 'alarm 3000; exec @ARGV' harbor run --path "$L/copies/$2" --agent $3 --env docker --job-name $1 --jobs-dir "$L/jobs" -y > "$L/logs/$1.log" 2>&1
  echo "$1 rc $? $(date +%T)"
}
run oracle-1 plain oracle
run oracle-2 plain oracle
run oracle-3 plain oracle
run owner-1 owner oracle
run nop-1 plain nop
run stub-1 stub oracle
run forgery-1 forgery oracle
echo ALL_DONE
