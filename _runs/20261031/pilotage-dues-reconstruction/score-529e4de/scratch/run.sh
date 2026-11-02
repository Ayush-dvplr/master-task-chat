for c in sample h1101 h1102 h1104 h1105 h1106; do
  mkdir -p /s/o_blind_$c; cd /tmp
  t0=$(date +%s.%N)
  perl -e 'alarm 600; exec @ARGV' python3 -B /b/derive_report.py --data /t/$c --out /s/o_blind_$c > /s/err_$c.txt 2>&1; rc=$?
  echo "TIME blind $c rc=$rc $(echo "$(date +%s.%N) - $t0" | bc)"
  tail -3 /s/err_$c.txt
  python3 -B /p/score4.py /t/t_$c.json /t/o_ref_$c /s/o_blind_$c blind_$c
done
echo ALL_DONE
