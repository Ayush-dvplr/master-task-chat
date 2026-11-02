#!/bin/sh
# Scratch: wave-1 Phase 2 kill test on the final generator (python:3.12-slim, WORK at /w).
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
cd "$P"
echo "== env"; python3 --version; nproc
echo "== gen"; python3 -B core2.py gen /tmp/core2 2>&1 | tail -8
jobs=/tmp/jobs.txt; : > "$jobs"
for w in 29 30 31 32 33 34 35 36; do
  for s in reference a_fast_dijkstra b_dominance c_incumbent d_bidirectional e_signature_keyed dijkstra greedy schema_only exhaustive; do
    echo "one $s /tmp/core2/world_$w" >> "$jobs"
  done
  for r in "$P/blind/src" "$P/opus/src" /w/repo_fixed/src; do
    echo "solve $r /tmp/core2/world_$w" >> "$jobs"
  done
done
while read -r m a f; do echo "$m $a $f"; done < "$jobs" | xargs -P 2 -L 1 sh -c '
mode=$0; a=$1; f=$2; t0=$(date +%s)
if [ "$mode" = one ]; then out=$(timeout 70 python3 -B core2.py one "$a" "$f" 70 2>&1 | tail -1); rc=$?; else out=$(timeout 70 python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1); rc=$?; fi
t1=$(date +%s); echo "ROW $mode $a $(basename $f) wall=$((t1-t0)) :: $out"'
echo ALL_DONE
