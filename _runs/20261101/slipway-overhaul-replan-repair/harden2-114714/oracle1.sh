set -e
mkdir -p /app/out; cp -R /b/environment/data /app/data
bash /b/solution/solve.sh
cd /w/h2_a3/proto && python3 -B diag2.py /b/tests /app/project /r/oracle1 SAMPLE_SEED EVAL_SEED CHALLENGE_SEED PROBE_SEED 4019474040292637395:groups 7627236482165915009:rules 650109135251380613:amendments 6227447286335280874:groups,rules,amendments
echo ALL_DONE
