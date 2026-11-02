#!/bin/sh
# usage: killall.sh "<hidden seeds>" "<shipped seeds>" "<solvers>" cap_seconds
cd /w
for s in $2; do
  for v in $3; do
    perl -e "alarm $4; exec @ARGV" python3 -B kill1.py shipped 6 1 $s $v || echo "ROW $v shipped $s $4 TIMEOUT_OR_CRASH rc=$?"
  done
done
for s in $1; do
  for v in $3; do
    perl -e "alarm $4; exec @ARGV" python3 -B kill1.py hidden 7 0.5 $s $v || echo "ROW $v hidden $s $4 TIMEOUT_OR_CRASH rc=$?"
  done
done
echo ALL_DONE
