cd "$(dirname "$0")"
for p in progs/*.py; do n=$(basename $p .py); python3 score2.py "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cohort-retention-reconciliation/tests/test_output.py" $p res/after_$n.json; done
echo ALL_DONE
