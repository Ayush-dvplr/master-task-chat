#!/bin/sh
# Redesign 1 kill run (inside container, /p = proto ro, /s = scratch rw).
# Usage: kill_r1.sh "<h_seed:empty:F..+F.. ...>" "<reader modes>"
set -u
cd /p
python3 -B gen_proto.py /s 2 "$1"
for d in /s/shipped /s/h*; do
  n=$(basename "$d")
  t0=$(date +%s.%N)
  READER=ref python3 -B solve_proto.py --data "$d/data" --out "$d/ref_out" >/dev/null 2>"$d/ref_err.txt"
  rc=$?; t1=$(date +%s.%N)
  echo "RUN ref $n rc=$rc sec=$(python3 -c "print(round($t1-$t0,2))")"
  for m in $2; do
    READER=$m perl -e 'alarm 60; exec @ARGV' python3 -B solve_proto.py --data "$d/data" --out "$d/m_$m" >/dev/null 2>"$d/err_$m.txt"
    echo "RUN $m $n rc=$? $(head -c 120 "$d/err_$m.txt" | tr '\n' ' ')"
  done
  perl -e 'alarm 60; exec @ARGV' python3 -B /p/blind/derive_report.py --data "$d/data" --out "$d/m_blind24" >/dev/null 2>"$d/err_blind24.txt"
  echo "RUN blind24 $n rc=$? $(tail -c 160 "$d/err_blind24.txt" | tr '\n' ' ')"
done
for m in $2 blind24; do
  echo "=== SCORE $m"
  OUTNAME=m_$m python3 -B scoreblind.py /s
done
echo ALL_DONE
