#!/bin/zsh
cd "$(dirname $0)"
L=../logs
for b in shipped hidden hidden_reorder uplift2 large; do
  t=$(date +%s)
  perl -e 'alarm 5400; exec @ARGV' python3 -B fuzz_local.py $b 1 300 6 > $L/fuzz_$b.jsonl 2> $L/fuzz_$b.err
  echo "$b rc=$? secs=$(( $(date +%s) - t ))" >> $L/fuzz_3a_summary.txt
done
echo ALL_DONE >> $L/fuzz_3a_summary.txt
