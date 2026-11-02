#!/bin/bash
export PYTHONPATH="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/slipway-overhaul-replan-repair/h2_a3/proto/stub" PYTHONDONTWRITEBYTECODE=1
SPECS=$(cat "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/specs.txt")
perl -e 'alarm 3000; exec @ARGV' python3 -B "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/slipway-overhaul-replan-repair/h2_a3/proto/diag2.py" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/slipway-overhaul-replan-repair/tests" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/slipway-overhaul-replan-repair/a3_program" "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/d_a3_program" $SPECS > "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/d_a3_program.log" 2>&1
echo "a3 rc $?"
python3 -B "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/slipway-overhaul-replan-repair/h2_a3/proto/score.py" "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/slipway-overhaul-replan-repair/tests/test_output.py" "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/d_a3_program.log" > "/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/fix2-2237/a3_score.txt" 2>&1
echo "score rc $?"
echo ALL_DONE
