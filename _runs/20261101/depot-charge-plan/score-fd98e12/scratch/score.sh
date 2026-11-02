for c in shipped1 hidden1 hidden2 hidden3 large1; do
  mkdir -p /w/$c
  t0=$(date +%s.%N)
  perl -e 'alarm 120; exec @ARGV' python3 -B /b/derive_report.py --data /d/$c/data --out /w/$c > /w/$c.stdout 2> /w/$c.stderr; rc=$?
  t1=$(date +%s.%N)
  echo "ROW $c rc $rc sec $(python3 -c "print(round($t1-$t0,2))") $(python3 -B /w/cmp.py /d/$c/ref /w/$c)"
done
echo ALL_DONE
