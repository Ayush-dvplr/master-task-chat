#!/bin/bash
# fix1 lanes, one at a time: QL oracle x3, QL nop, owner-only oracle, stub oracle.
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/fix1-20261101T1639/lanes"
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
  perl -e 'alarm 4200; exec @ARGV' harbor run -p "$2/hangar-check-replan" -a "$3" -k "$4" -n 1 -o "$L/jobs" --job-name "$1" -q -y > "logs/$1.log" 2>&1
  echo "LANE $1 rc=$? end $(date +%H:%M:%S)"
  tail -12 "logs/$1.log"
}
lane oracle ql oracle 3
lane nop ql nop 1
lane owner-only owner oracle 1
lane stub stub oracle 1
echo ALL_DONE
