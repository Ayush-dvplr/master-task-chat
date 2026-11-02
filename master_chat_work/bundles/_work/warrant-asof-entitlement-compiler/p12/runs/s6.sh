#!/bin/bash
# P12 4989b35: P7w (window fixed half, hr and start inferred) on the closed-window tiers of t7,
# verifier budget lifted so the lever, not the 2400 s budget, decides. -> s6_P7w.txt
set -u
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
R="$W/p12/runs"
TS=$(date +%Y%m%dT%H%M%S)-$(openssl rand -hex 2)
echo "TS $TS $(date +%H:%M:%S)" > "$R/s6.log"
ONLY=conv_2_dev_profile_exact,conv_2_prod_profile_exact,conv_6_dev_profile_exact,conv_6_prod_profile_exact,conv_8_dev_profile_exact,conv_8_prod_profile_exact
perl -e 'alarm 7200; exec @ARGV' docker run --rm --name "c4989b35_P7wc_$TS" --memory 4g --cpus 2 \
  -e PYTHONDONTWRITEBYTECODE=1 -e DELIVERED=0 -e TESTS=/p12/t7.py -e BUDGET=100000 -e CALL=3000 -e NODELIVER=1 \
  -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$B/tests":/tests:ro -v "$W/kill/P7w":/prog:ro \
  python:3.12-slim python3 /h/score.py /prog $ONLY > "$R/s6_P7w.txt" 2>&1
echo "s6 P7w rc=$? $(date +%H:%M:%S)" >> "$R/s6.log"
echo "ALL_DONE $(date +%H:%M:%S)" >> "$R/s6.log"
