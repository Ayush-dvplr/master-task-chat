#!/bin/bash
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler"; B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/warrant-asof-entitlement-compiler"
run() { perl -e 'alarm 2400; exec @ARGV' docker run --rm --name c4989b35_$1_20261030T085947-9b2d --memory 4g --cpus 2 -e PYTHONDONTWRITEBYTECODE=1 -e TESTS=/p12/t.py -v "$W/harness":/h:ro -v "$W/p12":/p12:ro -v "$B/tests":/tests:ro python:3.12-slim python3 /h/score.py /p12/$1 > "$W/p12/runs/score_$1.txt" 2>&1; echo "$1 rc=$?" ; }
run eng1 & run eng0 & wait
echo ALL_DONE
