set -u
cd /w/h2_a3/proto
for p in a3_program h2_a3/oracle_fixed oracle_program h2_a3/engine_orig h2_a3/variants/a3_groups h2_a3/variants/a3_rules h2_a3/variants/a3_amendments h2_a3/variants/a3_careful h2_a3/variants/oracle_less_groups h2_a3/variants/oracle_less_rules h2_a3/variants/oracle_less_amendments; do
  n=$(basename $p); python3 -B diag2.py /w/h2_a3/proto /w/$p /r/kill3_$n SAMPLE_SEED EVAL_SEED CHALLENGE_SEED PROBE_SEED 4019474040292637395:groups 7627236482165915009:rules 650109135251380613:amendments 6227447286335280874:groups,rules,amendments > /r/kill3_$n.log 2>&1; echo "$n rc $?"
done
python3 -B score.py /w/h2_a3/proto/test_output.py /r/kill3_*.log > /r/score3.log 2>&1; echo "score rc $?"
python3 -B scan.py /r/scan300b 300 groups,rules,amendments > /r/scan300b.log 2>&1; echo "scan rc $?"
echo ALL_DONE
