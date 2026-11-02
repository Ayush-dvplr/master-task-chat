set -u
S=/w/h2_a3/proto/stub
pip install --no-cache-dir -q harbor-rewardkit==0.2.1 > /r/f1_pip.log 2>&1; echo "pip rc $?"
apt-get update -qq > /dev/null 2>&1 && apt-get install -y -qq --no-install-recommends util-linux > /dev/null 2>&1; echo "apt rc $?"
# oracle solve with self-checks
mkdir -p /app/out; cp -R /b/environment/data /app/data
SOLUTION_ROOT=/b/solution bash /b/solution/solve.sh > /r/f1_solve.log 2>&1; echo "solve rc $?"
# tests-only verifier timing, oracle delivery
rm -rf /tmp/vt; cp -R /b/tests /tmp/vt; rm -f /tmp/vt/judge.toml
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/vt/reward.toml'); s=p.read_text()
p.write_text(s.replace('weights = { test_output = 0.005376344086021506, judge = 0.01282051282051282 }','weights = { test_output = 0.005376344086021506 }'))
PY
t0=$(date +%s); rewardkit /tmp/vt --workspace /app --output /r/vt_oracle.json > /r/vt_oracle.log 2>&1; echo "vt_oracle rc $? secs $(( $(date +%s) - t0 ))"
cp -R /app/project /r/f1_oracle_project 2>/dev/null
# a3 as delivered
rm -rf /app/out; mkdir -p /app/out; cp -R /a3/app/out/. /app/out/
t0=$(date +%s); rewardkit /tmp/vt --workspace /app --output /r/vt_a3.json > /r/vt_a3.log 2>&1; echo "vt_a3 rc $? secs $(( $(date +%s) - t0 ))"
# kill table on final tests
cd /w/h2_a3/proto
for p in a3_program h2_a3/oracle_fixed oracle_program h2_a3/engine_orig h2_a3/variants/a3_groups h2_a3/variants/a3_rules h2_a3/variants/a3_amendments h2_a3/variants/a3_careful h2_a3/variants/oracle_less_groups h2_a3/variants/oracle_less_rules h2_a3/variants/oracle_less_amendments; do
  n=$(basename $p); t0=$(date +%s); PYTHONPATH=$S python3 -B diag2.py /b/tests /w/$p /r/kill4_$n SAMPLE_SEED EVAL_SEED CHALLENGE_SEED PROBE_SEED 4019474040292637395:groups 7627236482165915009:rules 650109135251380613:amendments 6227447286335280874:groups,rules,amendments 8507130061071785379:groups,rules,amendments > /r/kill4_$n.log 2>&1; echo "$n rc $? secs $(( $(date +%s) - t0 ))"
done
PYTHONPATH=$S python3 -B score.py /b/tests/test_output.py /r/kill4_*.log > /r/score4.log 2>&1; echo "score rc $?"
echo ALL_DONE
