cd /p
for c in sample h1101 h1103 h1105; do
  t0=$(date +%s.%N); perl -e 'alarm 600; exec @ARGV' python3 -B solve3.py ref /s/$c /s/out_ref_$c; echo "ref $c rc=$? secs=$(echo "$(date +%s.%N) - $t0" | bc)"
done
for m in K1 K4w K4q; do for c in sample h1101 h1103 h1105; do
  t0=$(date +%s.%N); perl -e 'alarm 600; exec @ARGV' python3 -B solve3.py $m /s/$c /s/out_${m}_$c; echo "$m $c rc=$? secs=$(echo "$(date +%s.%N) - $t0" | bc)"
  python3 -B score3.py /s/t_$c.json /s/out_ref_$c /s/out_${m}_$c "$m/$c"
done; done
echo ALL_DONE
