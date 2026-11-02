#!/bin/bash
# runs inside env image: /w = proto (rw), /b = BUNDLE (ro)
export PYTHONDONTWRITEBYTECODE=1
R=/w/dout/P4.txt; : > $R
declare -A PROG=([solve]=/b/solution/solve.py [opus]=/w/progs/opus_derive_report.py [blind]=/w/progs/blind_derive_report.py)
FILES=$(ls /b/environment/data | grep -v '^schema.md$')
for v in solve opus blind; do
  P=${PROG[$v]}
  for f in $FILES; do
    d=/tmp/d_$v; rm -rf $d /tmp/o_$v; cp -r /b/environment/data $d; rm -f $d/$f; mkdir -p /tmp/o_$v
    timeout 120 python3 -B $P $d /tmp/o_$v >/tmp/log_$v 2>&1; rc=$?
    n=$(find /tmp/o_$v -type f | wc -l)
    pass=no; if [ $rc -ne 0 ] && [ $n -eq 0 ]; then pass=yes; fi
    echo "missing $v $f rc=$rc files=$n pass=$pass" >> $R
  done
  rm -rf /tmp/r1 /tmp/r2
  s=$(date +%s.%N); PYTHONHASHSEED=1 timeout 120 python3 -B $P /b/environment/data /tmp/r1 >/dev/null 2>&1; rc1=$?
  PYTHONHASHSEED=2 timeout 120 python3 -B $P /b/environment/data /tmp/r2 >/dev/null 2>&1; rc2=$?
  e=$(date +%s.%N)
  if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && diff -r /tmp/r1 /tmp/r2 >/dev/null; then same=yes; else same=no; fi
  echo "rerun $v rc1=$rc1 rc2=$rc2 identical=$same sec=$(echo "$e - $s" | bc 2>/dev/null)" >> $R
done
echo ALL_DONE >> $R
