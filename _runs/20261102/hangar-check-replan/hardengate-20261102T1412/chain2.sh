#!/bin/bash
# harden_r1 a1-as-delivered lane x2 (verifier seconds).
export OPENAI_API_KEY=unused
L="/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/hardengate-20261102T1412"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
cd "$L" || exit 1
wait_free() {
  for i in $(seq 180); do
    if python3 "$DF" --need-mb 4096 --cpus 2 | tail -1 | grep -q START=yes; then echo "dockfree START=yes $(date +%H:%M:%S)"; return 0; fi
    sleep 20
  done
  echo "dockfree never START=yes"; return 1
}
lane() { # name copy agent attempts
  wait_free || { echo "LANE $1 SKIPPED"; return; }
  echo "LANE $1 start $(date +%H:%M:%S)"
  yes | perl -e 'alarm 4200; exec @ARGV' harbor run -p "$2/hangar-check-replan" -a "$3" -k "$4" -n 1 -o "$L/jobs" --job-name "$1" -q -y > "logs/$1.log" 2>&1
  echo "LANE $1 rc=$? end $(date +%H:%M:%S)"
  tail -12 "logs/$1.log"
}
lane a1 a1 oracle 2
echo ALL_DONE
