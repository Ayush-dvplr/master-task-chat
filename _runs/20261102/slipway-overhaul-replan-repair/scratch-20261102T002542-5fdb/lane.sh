#!/bin/bash
# usage: lane.sh <k>
R="/Users/mac/Desktop/Terminal Bench/_runs/20261102/slipway-overhaul-replan-repair/qc-20261102T002542-5fdb"
J="$R/jobs"; L="$R/logs"
run() { echo "== $1 start $(date +%H:%M:%S)"; harbor run -p "$2" -a "$3" -o "$J" --env docker -y --job-name "$1"; echo "== $1 exit=$? $(date +%H:%M:%S)"; }
case "$1" in
1) for n in 1 2 3; do run oracle-$n "$R/copies/run/slipway-overhaul-replan-repair" oracle; done;;
2) run owner-1 "$R/copies/owner/slipway-overhaul-replan-repair" oracle;;
3) run nop-1 "$R/copies/run/slipway-overhaul-replan-repair" nop; run stub-1 "$R/copies/stub/slipway-overhaul-replan-repair" oracle;;
esac
echo LANE_DONE
