#!/bin/bash
# Law-1 fix 25c745d: per-project timing on old books + shipped data (Docker only)
run() { perl -e 'alarm 1500; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 \
  -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/tests":/tests:ro -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/environment/ci":/ci:ro -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote":/w:ro -v "/tmp/blind/cold-chain-backbone-quote-20261027T144736-9cb7/app":/blind:ro \
  warm-cold-chain-backbone-quote:w1 python -B /w/time_projects.py /tests/test_output.py "$1" "$2" "$3" /ci; }
run /blind/repo/src pkg eac8712
run /blind/repo/src dw dw_global
run /w/proto/probe_nospan/src pkg probe_nospan
run /w/proto/blind_d7a0_nospan/src pkg d7a0_nospan
run /w/proto/blind_2611_nospan/src pkg 2611_nospan
echo ALL_DONE
