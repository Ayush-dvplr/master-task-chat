#!/bin/sh
# usage: timing.sh "<n values>" "<hidden seeds>" "<solvers>" cap
cd /w
for n in $1; do
  for s in $2; do
    for v in $3; do
      perl -e "alarm $4; exec @ARGV" python3 -B kill1.py hidden $n 0.5 $s $v || echo "ROW $v hidden$n $s $4 TIMEOUT_OR_CRASH rc=$?"
    done
  done
done
echo ALL_DONE
