#!/bin/sh
# Scratch: gate v3.6 kill test on prototype worlds 37..46 (python:3.12-slim, WORK at /w).
# usage: kill3.sh PART FOLDER   PART = gen (generic solvers on worlds 37-41) | prog (programs on all worlds)
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
part=$1; root=$2
cd "$P"
echo "== env"; python3 --version; nproc
jobs=/tmp/jobs_$part.txt; : > "$jobs"
if [ "$part" = gen ]; then
  for w in 37 38 39 40 41; do
    for s in a_fast_dijkstra b_dominance c_incumbent d_bidirectional e_signature_keyed dijkstra greedy schema_only exhaustive astar; do
      echo "one $s $root/world_$w" >> "$jobs"
    done
  done
else
  for w in 37 38 39 40 41 42 43 44 45 46; do
    echo "one reference $root/world_$w" >> "$jobs"
    for r in "$P/a5/src" "$P/blind2/src" "$P/blind/src" "$P/opus/src" /w/repo_fixed/src; do
      echo "solve $r $root/world_$w" >> "$jobs"
    done
  done
fi
xargs -P 2 -L 1 sh -c '
mode=$0; a=$1; f=$2; t0=$(date +%s)
if [ "$mode" = one ]; then out=$(timeout 62 python3 -B core3.py one "$a" "$f" 2>&1 | tail -1); else out=$(timeout 62 python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1); fi
t1=$(date +%s); echo "ROW $mode $a $(basename $f) wall=$((t1-t0)) :: $out"' < "$jobs"
echo ALL_DONE
