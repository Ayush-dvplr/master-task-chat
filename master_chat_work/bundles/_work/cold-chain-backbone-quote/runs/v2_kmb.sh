#!/bin/bash
# kmb variant is built by w1_variants.py (variants.py has no kmb); rebuild and score after v2_chain ends.
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"; IMG=warm-cold-chain-backbone-quote:w1
DR="docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1"
A=/tmp/ccq_v2_app_20261028T123520-77ba; V=/tmp/ccq_v2_var_20261028T123520-77ba
until grep -q ALL_DONE "$W/runs/v2_chain.log"; do sleep 15; done
rm -rf $V/kmb
perl -e 'alarm 900; exec @ARGV' $DR -v $A:/oracle:ro -v $V:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/w1_variants.py /oracle kmb /var_out/kmb > /dev/null 2>&1; echo "kmb rc=$?"
find $V -name __pycache__ -prune -exec rm -rf {} +
echo "=== kmb new $(date +%H:%M:%S)"
perl -e 'alarm 2400; exec @ARGV' $DR -v $V/kmb:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py 2>&1 | grep -v "^ *$" | tail -48
echo ALL_DONE
