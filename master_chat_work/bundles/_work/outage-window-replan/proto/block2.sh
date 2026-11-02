#!/bin/bash
# oracle + nop through rebuilt tests, final hidden corpora ref/blind/check_exact, mutants, fire, kill2
mkdir -p /app && cp -r /srcdata /app/data
cd /d/proto
echo "== ORACLE"; for k in 1 2 3; do rm -rf /app/out; bash /solution/solve.sh > /tmp/solve_$k.log 2>&1; echo "solve.sh rc=$?"; t0=$(date +%s); python3 -B drive_tests.py /tests/test_output.py > /tmp/drv_$k.log 2>/dev/null; t1=$(date +%s); grep '^SCORE' /tmp/drv_$k.log; echo "verifier_s $((t1-t0))"; done
grep '^CHECK' /tmp/drv_1.log | grep FAIL; grep '^check' /tmp/solve_1.log
echo "== NOP"; rm -rf /app/out; python3 -B drive_tests.py /tests/test_output.py 2>/dev/null | tail -1
for c in h2 h3 n1 n2 n3; do
  rm -rf fin/ref_$c fin/blind_$c; mkdir -p fin/ref_$c fin/blind_$c
  t0=$(date +%s%N); python3 -B /solution/solve.py --data hidden/$c --out fin/ref_$c; rc=$?; t1=$(date +%s%N)
  echo "REF $c rc=$rc $(( (t1-t0)/1000000 ))ms"
  t0=$(date +%s%N); perl -e "alarm 60; exec @ARGV" python3 -B blind/derive_report.py --data hidden/$c --out fin/blind_$c >/dev/null 2>&1; rc=$?; t1=$(date +%s%N)
  echo "BLIND $c rc=$rc $(( (t1-t0)/1000000 ))ms $(python3 -B compare.py fin/ref_$c fin/blind_$c | tail -1)"
  python3 -B /d/check_exact.py hidden/$c fin/ref_$c | tail -1
done
echo ALL_DONE_A
cd /d; mkdir -p mutlogs2
for m in mut/*.py; do
  id=$(basename "$m" .py); rm -rf /app/out && mkdir -p /app/out; cp "$m" /app/out/derive_report.py
  python3 -B /app/out/derive_report.py --data /app/data --out /app/out > /dev/null 2>&1
  python3 -B proto/drive_tests.py /tests/test_output.py > "mutlogs2/$id.log" 2>/dev/null
  echo "MUT $id | $(grep '^SCORE' mutlogs2/$id.log) | $(grep '^CHECK' mutlogs2/$id.log | awk '/ FAIL /{print $2}' | tr '\n' ',')"
done
echo ALL_DONE_B
cd /d/proto
python3 -B fire.py 2 hidden/h2 hidden/h3 hidden/n1 hidden/n2 hidden/n3 | grep -E "^FIRE|^REGIONS_EXACT"
echo ALL_DONE_C
python3 -B kill2.py 60 hidden/h2 hidden/h3 hidden/n1 hidden/n2 hidden/n3
echo ALL_DONE_D
