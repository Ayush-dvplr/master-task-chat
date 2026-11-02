#!/bin/sh
# Scratch: gate v3.6 harden a4f790c kill test on gated core worlds 47..76 (python:3.12-slim, WORK at /w).
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
R=$P/gate_w
cd "$P"
echo "== env"; python3 --version; nproc
python3 -B gate.py gen "$R" 47 76
jobs=/tmp/jobs4.txt; : > "$jobs"
echo "solve300 /w/a6_repo/src $R/world_47" >> "$jobs"
echo "solve300 /w/a6_repo/src $R/world_48" >> "$jobs"
for w in $(seq 47 76); do
  echo "one strong $R/world_$w" >> "$jobs"
  echo "solve /w/a6_repo/src $R/world_$w" >> "$jobs"
done
for w in 49 52 55 58 61 64; do
  for r in "$P/a5/src" "$P/blind/src" "$P/blind2/src" "$P/opus/src" "$P/tb_d721/src" "$P/tb_d2fb/src" "$P/tb_9179/src" "$P/tb_b686/src" /w/repo_fixed/src; do
    echo "solve $r $R/world_$w" >> "$jobs"
  done
done
for w in 50 53 56 59 62; do
  for s in reference a_fast_dijkstra b_dominance c_incumbent d_bidirectional e_signature_keyed dijkstra greedy schema_only exhaustive astar; do
    echo "one $s $R/world_$w" >> "$jobs"
  done
done
xargs -P 2 -L 1 sh -c '
mode=$0; a=$1; f=$2; t0=$(date +%s)
case $mode in
  one) out=$(timeout 40 python3 -B gate.py one "$a" "$f" 2>&1 | tail -1);;
  solve) out=$(timeout 40 python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1);;
  solve300) out=$(timeout 300 python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1);;
esac
t1=$(date +%s); echo "ROW $mode $a $(basename $f) wall=$((t1-t0)) :: $out"' < "$jobs"
echo ALL_DONE
