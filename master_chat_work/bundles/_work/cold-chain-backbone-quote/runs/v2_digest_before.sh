#!/bin/bash
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -v "$W":/w -v "$B/environment/ci":/ci:ro -w /w warm-cold-chain-backbone-quote:w1 perl -e 'alarm 1500; exec @ARGV' python -B /w/v2_digest.py /w/p12v2_before/test_template.py /ci /w/runs/v2_digest_before.json
echo "EXIT $?"
