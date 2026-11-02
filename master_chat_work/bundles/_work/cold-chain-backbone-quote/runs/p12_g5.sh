#!/bin/bash
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
IMG=warm-cold-chain-backbone-quote:w1
for v in oracle shipped perlink kmb; do
  if [ $v = oracle ]; then app=/tmp/ccq_p12_app; else app=/tmp/ccq_p12_var/$v; fi
  echo "=== $v new $(date +%H:%M:%S)"
  perl -e 'alarm 1500; exec @ARGV' $DR -v "$app":/app -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/tests":/tests:ro -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | grep -v "^ *$" | tail -45
done
echo ALL_DONE
