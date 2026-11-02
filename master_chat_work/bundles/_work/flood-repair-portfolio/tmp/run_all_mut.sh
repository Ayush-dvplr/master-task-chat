cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio"
rm -f rule_results/done.txt mut_results/done3.txt
for f in rule_mut/*.py; do n=$(basename $f .py); python3 -B run_tests.py $f --json rule_results/$n.json > rule_results/$n.log 2>&1; echo "$n $?" >> rule_results/done.txt; done
echo ALL_DONE >> rule_results/done.txt
for f in mutants/*.py; do n=$(basename $f .py); python3 -B run_tests.py $f --json mut_results/$n.json > mut_results/$n.log 2>&1; echo "$n $?" >> mut_results/done3.txt; done
echo ALL_DONE >> mut_results/done3.txt
