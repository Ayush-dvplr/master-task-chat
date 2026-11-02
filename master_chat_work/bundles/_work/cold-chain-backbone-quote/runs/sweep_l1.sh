#!/bin/bash
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
perl -e 'alarm 1800; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e SWEEP_SKIP_WIDE=1 -w /w \
  -v "$B/tests":/tests:ro -v "$W":/w:ro warm-cold-chain-backbone-quote:w1 python -B /w/sweep300.py /tests/test_output.py 1 300 2
echo "rc=$?"
echo ALL_DONE
