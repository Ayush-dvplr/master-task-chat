#!/bin/bash
# usage: run.sh <prog_path_in_/p> <tag>   (/b bundle, /p programs, /w out)
set -u
prog=$1; tag=$2
mkdir -p /app/out /logs/verifier
cp -r /b/environment/data /app/data
cp -r /b/tests /tests
rm -f /tests/judge.toml
P=$(python3 -c "import re;print(sum(int(w) for w in re.findall(r'weight=(\d+)\)',open('/tests/test_output.py').read())))")
python3 -c "import sys;P=int(sys.argv[1]);open('/tests/reward.toml','w').write('[[reward]]\nname = \"reward\"\naggregation = \"weighted-sum\"\nweights = { test_output = %r }\n\n[scoring.test_output]\naggregation = \"weighted-sum\"\n' % (1/P))" $P
cp /p/$prog /app/out/derive_report.py
chown -R 1000:1000 /app
t0=$(date +%s)
(cd /app/out && python3 -B /app/out/derive_report.py --data /app/data --out /app/out) > /w/run_$tag.txt 2>&1
echo "run rc $? $(( $(date +%s)-t0 )) s"
t0=$(date +%s)
bash /tests/test.sh > /w/test_$tag.txt 2>&1; echo "test rc $? $(( $(date +%s)-t0 )) s"
for f in /logs/verifier/reward*.json; do cp $f /w/$(basename $f .json)_$tag.json; done
cat /logs/verifier/reward.json; echo
echo ALL_DONE
