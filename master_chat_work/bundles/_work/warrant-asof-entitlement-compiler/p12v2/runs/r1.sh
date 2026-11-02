#!/bin/bash
# P12 d872b22: changed checks on the fixed tests (BUNDLE tests) and on t_before for the probes.
set -u
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
R="$W/p12v2/runs"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
echo "TS $TS $(date +%H:%M:%S)" > "$R/r1.log"
POS=summary_identity_triangle,report_transcript_complete,artifacts_contract_layout,artifacts_parse_with_contract_shapes
ALL=$POS,negative_tool_ignores_input,negative_partial_output_on_missing_input,negative_report_digest_mismatch
sc() {
  local tag=$1 name=$2 src=$3 tests=$4 only=$5
  perl -e 'alarm 3600; exec @ARGV' docker run --rm --name "cd872b22_${tag}_${name}_$TS" --memory 4g --cpus 2 \
    -e PYTHONDONTWRITEBYTECODE=1 -e DELIVERED=0 -e TESTS=$tests \
    -v "$W/harness":/h:ro -v "$W/p12v2":/p12v2:ro -v "$B/tests":/tests:ro -v "$src":/prog:ro \
    python:3.12-slim python3 /h/score.py /prog $only > "$R/${tag}_$name.txt" 2>&1
  echo "$tag $name rc=$? $(date +%H:%M:%S)" >> "$R/r1.log"
}
rp() {
  perl -e 'alarm 3600; exec @ARGV' docker run --rm --name "cd872b22_rp_$TS" --memory 4g --cpus 2 \
    -e PYTHONDONTWRITEBYTECODE=1 -e DELIVERED=0 \
    -v "$W/harness":/h:ro -v "$W/p12v2":/p12v2:ro -v "$B/tests":/tests:ro -v "$W/p12/eng1":/prog:ro \
    python:3.12-slim python3 /p12v2/report_probe.py /prog > "$R/rp_eng1.txt" 2>&1
  echo "rp eng1 rc=$? $(date +%H:%M:%S)" >> "$R/r1.log"
}
laneA() {
  sc new const "$W/p12v2/probes/const" /tests/test_output.py $ALL
  sc old const "$W/p12v2/probes/const" /p12v2/t_before.py $ALL
  rp
  sc new partial "$W/p12v2/probes/partial" /tests/test_output.py $ALL
  sc old partial "$W/p12v2/probes/partial" /p12v2/t_before.py $ALL
  sc new a1 "$W/a1_program" /tests/test_output.py $POS
  sc new eng1 "$W/p12/eng1" /tests/test_output.py $POS
  sc new P0s "$W/kill/P0s" /tests/test_output.py $POS
}
laneB() {
  sc new P2n "$W/kill/P2n" /tests/test_output.py $POS
  sc new P3b "$W/kill/P3b" /tests/test_output.py $POS
  sc new P4o "$W/kill/P4o" /tests/test_output.py $POS
}
laneC() {
  sc new P6o "$W/kill/P6o" /tests/test_output.py $POS
  sc new P7w "$W/kill/P7w" /tests/test_output.py $POS
}
laneA & laneB & laneC & wait
echo "ALL_DONE $(date +%H:%M:%S)" >> "$R/r1.log"
