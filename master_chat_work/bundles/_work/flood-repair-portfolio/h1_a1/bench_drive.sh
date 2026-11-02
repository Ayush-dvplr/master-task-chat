#!/bin/bash
# args: list of "n rows pdiag seed" configs via CFG env; solvers via SOL env
cd /w/h1_a1
for cfg in $CFG; do
  IFS=, read n rows pd seed <<< "$cfg"
  for s in $SOL; do
    out=$(perl -e 'alarm shift; exec @ARGV' ${CAP:-60} python3 -B bench.py $s $n $rows $pd $seed 2>&1 | tail -2 | tr "\n" " ")
    rc=$?
    [ -z "$out" ] && out="$s $n $rows $pd $seed TIMEOUT"
    echo "$out"
  done
done
echo ALL_DONE
