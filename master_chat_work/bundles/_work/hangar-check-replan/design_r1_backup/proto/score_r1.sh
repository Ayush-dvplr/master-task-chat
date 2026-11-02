#!/bin/sh
# Score a design blind program against the reference (inside container, /p = proto ro, /s = scratch rw, /b = blind dir ro).
# Usage: score_r1.sh "<h_seed:empty:F..+F.. ...>" <name>
set -u
cd /p
python3 -B gen_proto.py /s 2 "$1"
for d in /s/shipped /s/h*; do
  n=$(basename "$d")
  t0=$(date +%s.%N)
  READER=ref python3 -B solve_proto.py --data "$d/data" --out "$d/ref_out" >/dev/null 2>"$d/ref_err.txt"
  rc=$?; t1=$(date +%s.%N)
  echo "RUN ref $n rc=$rc sec=$(python3 -c "print(round($t1-$t0,2))")"
  t0=$(date +%s.%N)
  perl -e 'alarm 60; exec @ARGV' python3 -B /b/derive_report.py --data "$d/data" --out "$d/m_$2" >/dev/null 2>"$d/err_$2.txt"
  rc=$?; t1=$(date +%s.%N)
  echo "RUN $2 $n rc=$rc sec=$(python3 -c "print(round($t1-$t0,2))") $(tail -c 160 "$d/err_$2.txt" | tr '\n' ' ')"
done
echo "=== SCORE $2"
OUTNAME=m_$2 python3 -B scoreblind.py /s
echo ALL_DONE
