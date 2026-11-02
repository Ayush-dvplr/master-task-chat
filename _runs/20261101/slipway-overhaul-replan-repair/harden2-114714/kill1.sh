set -u
cd /w/h2_a3/proto
for p in a3_program h2_a3/oracle_fixed; do
  n=$(basename $p); python3 -B diag2.py /w/h2_a3/proto /w/$p /r/kill1_$n SAMPLE_SEED EVAL_SEED CHALLENGE_SEED PROBE_SEED 4019474040292637395:groups 7627236482165915009:rules 650109135251380613:amendments 6227447286335280874:groups,rules,amendments > /r/kill1_$n.log 2>&1; echo "$n rc $?"
done
echo ALL_DONE
