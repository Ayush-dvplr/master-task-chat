cd /p
for m in ref K1 K2 K4 K4w K4q; do for c in shipped h1101 h1102 h1103 h1104; do
  perl -e 'alarm 600; exec @ARGV' python3 -B kill2.py $m /s/$c.json /s/out_${m}_$c.json || echo "$m $c RC=$?"
  python3 -B score2.py /s/$c.json /s/out_${m}_$c.json
done; done
echo ALL_DONE
