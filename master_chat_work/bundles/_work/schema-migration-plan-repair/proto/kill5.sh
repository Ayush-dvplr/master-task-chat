#!/bin/sh
# Scratch: gate v3.7 redesign 9111ecc kill test on gated core worlds 47..98 at the per-world child cap of 20 s
# (python:3.12-slim, WORK at /w, 2 parallel jobs, wall cap per job with perl alarm).
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
R=/tmp/gate5
cd "$P"
echo "== env"; python3 --version; nproc
t0=$(date +%s)
python3 -B gate.py gen "$R" 47 98
t1=$(date +%s); echo "GEN_TOTAL $((t1-t0)) s for 52 worlds"
jobs=/tmp/jobs5.txt; : > "$jobs"
for w in $(seq 47 98); do
  echo "one strong $R/world_$w" >> "$jobs"
  echo "solve /w/a6_repo/src $R/world_$w" >> "$jobs"
  echo "solve /w/repo_fixed/src $R/world_$w" >> "$jobs"
done
for w in 77 81 85 89 93 97; do
  for r in "$P/a5/src" "$P/blind/src" "$P/blind2/src" "$P/opus/src" "$P/tb_d721/src" "$P/tb_d2fb/src" "$P/tb_9179/src" "$P/tb_b686/src"; do
    echo "solve $r $R/world_$w" >> "$jobs"
  done
done
for w in 78 84 90 96; do
  for s in reference a_fast_dijkstra b_dominance c_incumbent d_bidirectional e_signature_keyed dijkstra greedy schema_only exhaustive astar; do
    echo "one $s $R/world_$w" >> "$jobs"
  done
done
xargs -P 2 -L 1 sh -c '
mode=$0; a=$1; f=$2; t0=$(date +%s)
case $mode in
  one) out=$(perl -e "alarm 20; exec @ARGV" python3 -B gate.py one "$a" "$f" 2>&1 | tail -1);;
  solve) out=$(perl -e "alarm 20; exec @ARGV" python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1);;
esac
t1=$(date +%s); echo "ROW $mode $a $(basename $f) wall=$((t1-t0)) :: $out"' < "$jobs"
echo ALL_DONE
