#!/bin/bash
# P12 4989b35: altered_config_outputs_exact only, on the final tests (t6), one container at a time.
set -u
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
R="$W/p12/runs"
TS=20261030T$(date +%H%M)-s4
one() {
  local name=$1 src=$2 deliv=$3
  perl -e 'alarm 2400; exec @ARGV' docker run --rm --name "c4989b35_${name}_$TS" --memory 4g --cpus 2 \
    -e PYTHONDONTWRITEBYTECODE=1 -e DELIVERED=$deliv -e TESTS=/p12/t6.py \
    -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$B/tests":/tests:ro -v "$src":/prog:ro \
    python:3.12-slim python3 /h/score.py /prog altered_config_outputs_exact > "$R/s4_$name.txt" 2>&1
  echo "$name rc=$? $(date +%H:%M:%S)" >> "$R/s4.log"
}
: > "$R/s4.log"
one b92419ce /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9b7d/out 1
one b787e598 /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-9992/out 1
one bb6c896c /tmp/blind/warrant-asof-entitlement-compiler-20261030T060705-cee9/out 1
one a1 "$W/a1_program" 0
one eng1 "$W/p12/eng1" 0
echo "ALL_DONE $(date +%H:%M:%S)" >> "$R/s4.log"
