#!/bin/bash
# usage: run.sh <alarm_s> <corpus>...
A=$1; shift
cd /d/proto
for c in "$@"; do
  mkdir -p scale/ref_$c scale/blind_$c
  t0=$(date +%s%N); perl -e "alarm $A; exec @ARGV" python3 -B solve_proto.py --data scale/$c --out scale/ref_$c; rc=$?; t1=$(date +%s%N)
  echo "REF $c rc=$rc $(( (t1-t0)/1000000 ))ms"
  t0=$(date +%s%N); perl -e "alarm $A; exec @ARGV" python3 -B blind/derive_report.py --data scale/$c --out scale/blind_$c >/dev/null 2>&1; rc=$?; t1=$(date +%s%N)
  echo "BLIND $c rc=$rc $(( (t1-t0)/1000000 ))ms $(python3 -B compare.py scale/ref_$c scale/blind_$c | tail -1)"
done
echo ALL_DONE
