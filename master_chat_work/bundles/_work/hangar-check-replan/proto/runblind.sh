#!/bin/sh
# Usage (inside container, /p = proto ro, /s = scratch rw): runblind.sh "<h_seed:empty ...>"
# Generates shipped seed 1 + hidden corpora, runs solve_proto (ref_out) and blind (blind_out, 60 s alarm).
set -u
cd /p
python3 -B gen_proto.py /s 1 "$1"
for d in /s/shipped /s/h*; do
  n=$(basename "$d")
  python3 -B solve_proto.py --data "$d/data" --out "$d/ref_out" >/dev/null 2>"$d/ref_err.txt"
  echo "REF $n rc=$?"
  t0=$(date +%s.%N)
  perl -e 'alarm 60; exec @ARGV' python3 -B /p/blind/derive_report.py --data "$d/data" --out "$d/blind_out" >"$d/blind_stdout.txt" 2>"$d/blind_err.txt"
  rc=$?
  t1=$(date +%s.%N)
  echo "BLIND $n rc=$rc sec=$(python3 -c "print(round($t1-$t0,2))")"
done
echo ALL_DONE
