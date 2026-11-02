#!/bin/bash
# fix2 lane: tests-only oracle x3 (solution changed; tests unchanged so nop/owner/stub not rerun).
L="/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/fix2-20261101T2235/lanes"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
cd "$L" || exit 1
for i in $(seq 180); do
  if python3 "$DF" --need-mb 4096 --cpus 2 | tail -1 | grep -q START=yes; then echo "dockfree START=yes $(date +%H:%M:%S)"; break; fi
  sleep 20
done
echo "LANE oracle start $(date +%H:%M:%S)"
perl -e 'alarm 4200; exec @ARGV' harbor run -p "$L/ql/hangar-check-replan" -a oracle -k 3 -n 1 -o "$L/jobs" --job-name oracle -q -y > logs/oracle.log 2>&1
echo "LANE oracle rc=$? end $(date +%H:%M:%S)"
tail -12 logs/oracle.log
echo ALL_DONE
