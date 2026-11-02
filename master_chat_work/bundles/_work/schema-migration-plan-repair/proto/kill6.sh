#!/bin/sh
# Scratch: gate v3.7 redesign 9111ecc extra kill test on gated core worlds 99..106 at the per-world child cap of 15 s
# (python:3.12-slim, WORK at /w, 2 parallel jobs, wall cap per job with perl alarm).
set -u
export PYTHONDONTWRITEBYTECODE=1
P=/w/proto
R=/tmp/gate6
cd "$P"
echo "== env"; python3 --version; nproc
t0=$(date +%s)
python3 -B gate.py gen "$R" 99 106
t1=$(date +%s); echo "GEN_TOTAL $((t1-t0)) s for 8 worlds"
jobs=/tmp/jobs6.txt; : > "$jobs"
for w in $(seq 99 106); do
  echo "one strong $R/world_$w" >> "$jobs"
  echo "solve /w/a6_repo/src $R/world_$w" >> "$jobs"
  echo "solve /w/repo_fixed/src $R/world_$w" >> "$jobs"
done
xargs -P 2 -L 1 sh -c '
mode=$0; a=$1; f=$2; t0=$(date +%s)
case $mode in
  one) out=$(perl -e "alarm 15; exec @ARGV" python3 -B gate.py one "$a" "$f" 2>&1 | tail -1);;
  solve) out=$(perl -e "alarm 15; exec @ARGV" python3 -B core2.py solve "$a" "$f" 2>&1 | tail -1);;
esac
t1=$(date +%s); echo "ROW $mode $a $(basename $f) wall=$((t1-t0)) :: $out"' < "$jobs"
echo ALL_DONE
