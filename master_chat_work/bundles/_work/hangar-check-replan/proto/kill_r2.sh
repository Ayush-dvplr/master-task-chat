#!/bin/sh
# Redesign 2 kill run (inside container, /p = proto ro, /s = scratch rw).
# Usage: kill_r2.sh "<h_seed:empty::stype ...>" "<settle slip modes>"
set -u
cd /p
python3 -B gen_proto.py /s 2 "$1"
for d in /s/shipped /s/h*; do
  n=$(basename "$d")
  python3 -B -c "import json;m=json.load(open('$d/abstract.json'))['meta'];print('META $n', {k:m.get(k) for k in ('stype','A','U','U_b','grants','pair')})"
  t0=$(date +%s.%N)
  SETTLE=ref python3 -B solve_proto.py --data "$d/data" --out "$d/ref_out" >/dev/null 2>"$d/ref_err.txt"
  rc=$?; t1=$(date +%s.%N)
  echo "RUN ref $n rc=$rc sec=$(python3 -c "print(round($t1-$t0,2))") $(head -c 160 "$d/ref_err.txt" | tr '\n' ' ')"
  for m in $2; do
    SETTLE=$m perl -e 'alarm 60; exec @ARGV' python3 -B solve_proto.py --data "$d/data" --out "$d/m_$m" >/dev/null 2>"$d/err_$m.txt"
    echo "RUN $m $n rc=$? $(head -c 160 "$d/err_$m.txt" | tr '\n' ' ')"
  done
  for b in blind24:/p/blind blindr1:/p/blind_r1; do
    nm=${b%%:*}; dir=${b#*:}
    perl -e 'alarm 60; exec @ARGV' python3 -B "$dir/derive_report.py" --data "$d/data" --out "$d/m_$nm" >/dev/null 2>"$d/err_$nm.txt"
    echo "RUN $nm $n rc=$? $(tail -c 160 "$d/err_$nm.txt" | tr '\n' ' ')"
  done
done
for m in $2 blind24 blindr1; do
  for v in settle all plan; do
    echo "=== SCORE $m VIEW $v"
    VIEW=$v OUTNAME=m_$m python3 -B scoreblind.py /s | grep -v "^  " 
  done
done
echo ALL_DONE
