#!/bin/bash
perl -e 'alarm 1500; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e CAP=200 -e MAXCAPS=3 -e BOOKS=shipped \
  -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/tests":/tests:ro -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/environment/ci":/ci:ro -v "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote":/w:ro \
  warm-cold-chain-backbone-quote:w1 python -B /w/time_projects.py /tests/test_output.py /w/proto/blind_2611_nospan/src pkg 2611_nospan /ci
echo ALL_DONE
