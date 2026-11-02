#!/bin/bash
# P12 4989b35 (restart after master kill 10:27): final tests t7 (conv_6 seed 98123).
# Full scores for the s3 rows never finished (P3b, P6o, P7w) -> s3r_<name>.txt;
# UNIQ proof for 98123 -> s5_uniq.txt; conv_6 dev/prod for every other program -> s5_<name>.txt.
set -u
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
R="$W/p12/runs"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
echo "TS $TS $(date +%H:%M:%S)" > "$R/s5.log"
sc() {
  local tag=$1 name=$2 src=$3 deliv=$4 only=$5
  perl -e 'alarm 3000; exec @ARGV' docker run --rm --name "c4989b35_${name}_$TS" --memory 4g --cpus 2 \
    -e PYTHONDONTWRITEBYTECODE=1 -e DELIVERED=$deliv -e TESTS=/p12/t7.py \
    -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$B/tests":/tests:ro -v "$src":/prog:ro \
    python:3.12-slim python3 /h/score.py /prog $only > "$R/${tag}_$name.txt" 2>&1
  echo "$tag $name rc=$? $(date +%H:%M:%S)" >> "$R/s5.log"
}
C6=conv_6_dev_profile_exact,conv_6_prod_profile_exact
uniq() {
  perl -e 'alarm 3000; exec @ARGV' docker run --rm --name c4989b35_uniq_$TS --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e REF=/p12/t7.py -e UNIQ=1 -e STARTS=requested,decided,recorded,latest \
    -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$W":/w:ro python:3.12-slim python3 /h/conv_sweep.py - \
    98123:0.05:conv:zone=Site/Brisk:requested:closed > "$R/s5_uniq.txt" 2>&1
  echo "s5 uniq rc=$? $(date +%H:%M:%S)" >> "$R/s5.log"
}
laneA() {
  sc s3r P3b "$W/kill/P3b" 0 ""
  sc s3r P7w "$W/kill/P7w" 0 ""
  uniq
  sc s5 eng1 "$W/p12/eng1" 0 $C6
  sc s5 P4o "$W/kill/P4o" 0 $C6
}
laneB() {
  sc s3r P6o "$W/kill/P6o" 0 ""
  sc s5 a1 "$W/a1_program" 0 $C6
  sc s5 b92419ce /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9b7d/out 1 $C6
  sc s5 b787e598 /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9992/out 1 $C6
  sc s5 bb6c896c /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-cee9/out 1 $C6
  sc s5 P0s "$W/kill/P0s" 0 $C6
  sc s5 P2n "$W/kill/P2n" 0 $C6
}
laneA & laneB & wait
echo "ALL_DONE $(date +%H:%M:%S)" >> "$R/s5.log"
