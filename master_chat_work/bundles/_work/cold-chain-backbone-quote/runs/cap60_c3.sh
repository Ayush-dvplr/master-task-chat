#!/bin/zsh
A=/tmp/ccq_cap60_20261030T120047-97ea
IMG=warm-cold-chain-backbone-quote:l1
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
echo start $(date)
perl -e 'alarm 900; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e APP_ROOT=/app -v $A/oracle:/app -v "$B/solution":/solution:ro $IMG python -B /solution/solve.py > $A/solve.log 2>&1; echo solve rc $?
perl -e 'alarm 1500; exec @ARGV' docker run --rm --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e APP_ROOT=/app -v $A/oracle:/app -v "$B/tests":/tests:ro -v "$W":/w:ro $IMG python -B /w/time_books.py /tests/test_output.py; echo time rc $?
echo ALL_DONE $(date)
