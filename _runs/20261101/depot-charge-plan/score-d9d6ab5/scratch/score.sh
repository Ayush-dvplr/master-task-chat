for c in shipped1 hidden1 hidden2 hidden3 large1; do
  mkdir -p /w/$c/blind; cp -r /old/$c/data /w/$c/; cp -r /old/$c/ref /w/$c/
done
for k in hidden:4 hidden:5 hidden:6; do
  kind=${k%%:*}; seed=${k##*:}; c=$kind$seed
  mkdir -p /w/$c/blind
  python3 -B /p/render.py $seed $kind /w/$c/data && python3 -B /p/bf.py /w/$c/data /w/$c > /w/$c/bf.txt 2>&1; echo "BF $c $(tail -1 /w/$c/bf.txt)"
done
for c in shipped1 hidden1 hidden2 hidden3 hidden4 hidden5 hidden6 large1; do
  t0=$(date +%s.%N)
  perl -e 'alarm 120; exec @ARGV' python3 -B /b/derive_report.py --data /w/$c/data --out /w/$c/blind > /w/$c/blind.stdout 2> /w/$c/blind.stderr; rc=$?
  t1=$(date +%s.%N)
  echo "BLIND $c rc $rc sec $(python3 -c "print(round($t1-$t0,2))") $(python3 -B /w/cmp2.py /w/$c/ref /w/$c/blind)"
done
echo ALL_DONE
