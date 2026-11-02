cd /p
for c in sample h1101 h1102 h1104 h1105 h1106; do
  t0=$(date +%s.%N)
  perl -e 'alarm 600; exec @ARGV' python3 -B solve4.py ref /s/$c /s/o_ref_$c; rc=$?
  echo "TIME ref $c rc=$rc $(echo "$(date +%s.%N) - $t0" | bc)"
done
for m in K1 K2 K4w; do
  for c in sample h1101 h1102 h1104 h1105 h1106; do
    t0=$(date +%s.%N)
    perl -e 'alarm 600; exec @ARGV' python3 -B solve4.py $m /s/$c /s/o_${m}_$c; rc=$?
    echo "TIME $m $c rc=$rc $(echo "$(date +%s.%N) - $t0" | bc)"
    python3 -B score4.py /s/t_$c.json /s/o_ref_$c /s/o_${m}_$c ${m}_$c
  done
done
echo ALL_DONE
