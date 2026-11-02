#!/bin/bash
cd "$(dirname "$0")"
export TOTAL=1 PYTHONDONTWRITEBYTECODE=1
for s in 31 33 34; do
  for v in ref ref3 bnb_ord bnb dp dfs_plain; do
    python3 -B bench.py $v p_e6_$s.json 120 r_${v}_e6_$s.json > log_${v}_e6_$s.txt 2>&1 &
  done
  wait
done
echo ALL_DONE > runall.done
