#!/bin/sh
# Scratch: wave-1 kill test inside python:3.12-slim, 2 CPUs, 4 GB (WORK mounted at /w).
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
cd "$P"
echo "== env"; python3 --version; nproc
echo "== design1 gen"; python3 -B history.py /tmp/hist 4 40 8 2>&1 | tail -4
for v in plain name_keyed end_resolve file_order greedy; do
  echo "== design1 opus $v"; python3 -B run_solver.py "$P/opus/src" /tmp/hist "$v" 2>&1 | tail -4
done
echo "== design1 blind plain"; python3 -B run_solver.py "$P/blind/src" /tmp/hist plain 2>&1 | tail -4
echo "== design1 oracle plain"; python3 -B run_solver.py /w/repo_fixed/src /tmp/hist plain 2>&1 | tail -4
echo "== design2 gen"; python3 -B core.py gen /tmp/core 8 1000 2>&1 | tail -8
for g in astar greedy schema_only exhaustive dijkstra; do
  echo "== design2 prog $g"; python3 -B core.py prog "$g" /tmp/core 10 2>&1 | tail -24
done
for r in blind opus; do
  echo "== design2 solve $r"; python3 -B core.py solve "$P/$r/src" /tmp/core 10 2>&1 | tail -24
done
echo "== design2 solve oracle"; python3 -B core.py solve /w/repo_fixed/src /tmp/core 10 2>&1 | tail -24
echo "== design2 slow-solver full time (first payload, limit 120)"
FIRST=1 python3 -B core.py solve "$P/opus/src" /tmp/core 120 2>&1 | head -3
FIRST=1 python3 -B core.py solve "$P/blind/src" /tmp/core 120 2>&1 | head -3
for r in blind opus; do echo "== p4 $r"; python3 -B p4.py "$P/$r/src" /tmp/hist 2>&1 | tail -3; done
echo "== p4 oracle"; python3 -B p4.py /w/repo_fixed/src /tmp/hist 2>&1 | tail -3
echo ALL_DONE
