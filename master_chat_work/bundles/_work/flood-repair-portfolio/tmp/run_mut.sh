cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio"
for f in mutants/*.py; do n=$(basename $f .py); python3 -B run_tests.py $f --json mut_results/$n.json > mut_results/$n.log 2>&1; echo "$n $?" >> mut_results/done.txt; done
echo ALL_DONE >> mut_results/done.txt
