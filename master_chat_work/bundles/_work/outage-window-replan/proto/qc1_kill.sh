#!/bin/bash
# P12 qc1: reference seconds per fixed graded corpus, then kill2 rows (60 s budget) on them
cd /d/proto; mkdir -p /tmp/fin
for c in h2 h3; do
  t0=$(date +%s%N); python3 -B /solution/solve.py --data hidden_qc1/$c --out /tmp/fin/ref_$c; rc=$?; t1=$(date +%s%N)
  echo "REF $c rc=$rc $(( (t1-t0)/1000000 )) ms"
done
python3 -B kill2.py 60 hidden_qc1/h2 hidden_qc1/h3
echo ALL_DONE
