#!/bin/bash
# nop through tests, then per final hidden corpus: solve.py, blind (alarm 60), fire, kill2 60
cd /d/proto
mkdir -p /app && cp -r /srcdata /app/data
echo "== NOP"; python3 -B /d/proto/drive_tests.py /tests/test_output.py | tail -3
for c in h2 h3 n1 n2 n3; do
  mkdir -p fin/ref_$c fin/blind_$c
  t0=$(date +%s%N); python3 -B /solution/solve.py --data hidden/$c --out fin/ref_$c; rc=$?; t1=$(date +%s%N)
  echo "REF $c rc=$rc $(( (t1-t0)/1000000 ))ms"
  t0=$(date +%s%N); perl -e "alarm 60; exec @ARGV" python3 -B blind/derive_report.py --data hidden/$c --out fin/blind_$c >/dev/null 2>&1; rc=$?; t1=$(date +%s%N)
  echo "BLIND $c rc=$rc $(( (t1-t0)/1000000 ))ms $(python3 -B compare.py fin/ref_$c fin/blind_$c | tail -1)"
  python3 -B /d/check_exact.py hidden/$c fin/ref_$c | tail -2
done
python3 -B fire.py 2 hidden/h2 hidden/h3 hidden/n1 hidden/n2 hidden/n3 | grep -E "^FIRE|^REGIONS_EXACT"
echo ALL_DONE_A
python3 -B kill2.py 60 hidden/h2 hidden/h3 hidden/n1 hidden/n2 hidden/n3
echo ALL_DONE_B
