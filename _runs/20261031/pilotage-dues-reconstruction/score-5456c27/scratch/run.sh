cd /p
for c in sample h1101 h1103 h1105; do
  t0=$(date +%s.%N); perl -e 'alarm 600; exec @ARGV' python3 -B solve3.py ref /s/$c /s/out_ref_$c; echo "ref $c rc=$? secs=$(echo "$(date +%s.%N) - $t0" | bc)"
done
for c in sample h1101 h1103 h1105; do
  mkdir -p /s/out_blind_$c
  t0=$(date +%s.%N); perl -e 'alarm 600; exec @ARGV' python3 -B /s/blind/derive_report.py --data /s/$c --out /s/out_blind_$c 2>/s/blind_err_$c.txt; echo "blind $c rc=$? secs=$(echo "$(date +%s.%N) - $t0" | bc)"
  tail -6 /s/blind_err_$c.txt
  python3 -B score3.py /s/t_$c.json /s/out_ref_$c /s/out_blind_$c "blind/$c"
done
echo ALL_DONE
