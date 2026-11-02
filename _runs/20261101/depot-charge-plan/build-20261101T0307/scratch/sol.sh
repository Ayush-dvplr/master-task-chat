for c in shipped hidden_61207 hidden_72931 hidden_84419 large_93503; do
  rm -rf /w/sol/$c; mkdir -p /w/sol/$c
  s=$(date +%s.%N)
  python3 -B /s/solve.py --data /w/$c/data --out /w/sol/$c > /w/sol/$c.log 2>&1; rc=$?
  e=$(date +%s.%N)
  echo "RUN $c rc $rc sec $(python3 -c "print(round($e-$s,2))")"; tail -3 /w/sol/$c.log
  python3 -B /t/diffout.py /w/$c/ref /w/sol/$c
done
echo ALL_DONE
