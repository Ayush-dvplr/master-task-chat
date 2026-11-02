#!/bin/bash
# usage: run.sh <oracle|nop> <tag>
set -u
mode=$1; tag=$2
mkdir -p /app /logs/verifier
cp -r /b/environment/data /app/data
cp -r /b/tests /tests
rm -f /tests/judge.toml
P=$(python3 -c "import re;print(sum(int(w) for w in re.findall(r'weight=(\d+)\)',open('/tests/test_output.py').read())))")
python3 -c "import sys;P=int(sys.argv[1]);open('/tests/reward.toml','w').write('[[reward]]\nname = \"reward\"\naggregation = \"weighted-sum\"\nweights = { test_output = %r }\n\n[scoring.test_output]\naggregation = \"weighted-sum\"\n' % (1/P))" $P
if [ "$mode" = oracle ]; then cp -r /b/solution /solution; chown -R 1000:1000 /app; t0=$(date +%s); bash /solution/solve.sh > /w/solve_$tag.txt 2>&1; echo "solve rc $? $(( $(date +%s)-t0 )) s"; fi
t0=$(date +%s)
bash /tests/test.sh > /w/test_$tag.txt 2>&1; echo "test rc $? $(( $(date +%s)-t0 )) s"
cp /logs/verifier/reward*.json /w/ 2>/dev/null; for f in /logs/verifier/reward*.json; do cp $f /w/$(basename $f .json)_$tag.json; done
cat /logs/verifier/reward.json; echo
echo ALL_DONE
