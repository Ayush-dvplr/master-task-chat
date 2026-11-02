#!/bin/bash
cd "/Users/mac/Desktop/Terminal Bench/_runs/20261102/depot-charge-plan/a2score-20261102T0028/scratch"
L=../logs
t=$(date +%s)
KEEP=1 perl -e 'alarm 5400; exec @ARGV' python3 -B targeted.py all 1 60 4 > $L/targeted_all.jsonl 2> $L/targeted_all.err
echo "all rc=$? secs=$(( $(date +%s)-t ))" >> $L/targeted_summary.txt
t=$(date +%s)
KEEP=1 perl -e 'alarm 1800; exec @ARGV' python3 -B targeted.py blank_lines 1 20 4 > $L/targeted_blank.jsonl 2> $L/targeted_blank.err
echo "blank rc=$? secs=$(( $(date +%s)-t ))" >> $L/targeted_summary.txt
echo ALL_DONE >> $L/targeted_summary.txt
