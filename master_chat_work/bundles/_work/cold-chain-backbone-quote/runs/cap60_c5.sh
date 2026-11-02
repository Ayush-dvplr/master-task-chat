#!/bin/zsh
A=/tmp/ccq_cap60_20261030T120047-97ea
IMG=warm-cold-chain-backbone-quote:l1
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
while ! grep -q ALL_DONE "$W/runs/cap60_c4b.log" 2>/dev/null; do sleep 20; done
echo start $(date)
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v $A/oracle:/oracle:ro -v $A:/var_out -v "$W":/w:ro -w /w $IMG python -B /w/cap60_hang.py /oracle /var_out/v_hang; echo hang build rc $?
S=$(date +%s)
perl -e 'alarm 3000; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e APP_ROOT=/app -v $A/v_hang:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/run_local_tests.py /app /tests/test_output.py > "$W/runs/cap60_score_v_hang.log" 2>&1; echo score v_hang rc $? elapsed $(( $(date +%s) - S )) s
grep SCORE "$W/runs/cap60_score_v_hang.log"
echo ALL_DONE $(date)
