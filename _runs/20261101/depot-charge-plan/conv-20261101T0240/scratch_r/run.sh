for k in shipped:1 hidden:1 hidden:2 hidden:3 large:1; do
  kind=${k%%:*}; seed=${k##*:}; c=$kind$seed
  python3 -B /p/render.py $seed $kind /w/$c/data && python3 -B /p/bf.py /w/$c/data /w/$c
  mkdir -p /w/$c/blind
  perl -e 'alarm 120; exec @ARGV' python3 -B /b/derive_report.py --data /w/$c/data --out /w/$c/blind > /w/$c/blind.stdout 2> /w/$c/blind.stderr; rc=$?
  echo "BLIND $c rc $rc $(python3 -B /w/cmp.py /w/$c/ref /w/$c/blind)"
done
echo ALL_DONE
