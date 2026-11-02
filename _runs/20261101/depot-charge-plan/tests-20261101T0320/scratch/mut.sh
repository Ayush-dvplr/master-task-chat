#!/bin/bash
# usage: mut.sh  (runs every /m/*.py through the real tests)
set -u
cp -r /b/tests /tests0
P=$(python3 -c "import re;print(sum(int(w) for w in re.findall(r'weight=(\d+)\)',open('/tests0/test_output.py').read())))")
for m in $(ls /m/*.py | awk -v p=${PART:-0} "NR%2==p"); do
  cd /
  n=$(basename $m .py)
  rm -rf /app /tests /logs; mkdir -p /app/out /logs/verifier
  cp -r /b/environment/data /app/data; cp -r /tests0 /tests; rm -f /tests/judge.toml
  python3 -c "import sys;P=int(sys.argv[1]);open('/tests/reward.toml','w').write('[[reward]]\nname = \"reward\"\naggregation = \"weighted-sum\"\nweights = { test_output = %r }\n\n[scoring.test_output]\naggregation = \"weighted-sum\"\n' % (1/P))" $P
  cp $m /app/out/derive_report.py; chown -R 1000:1000 /app
  setpriv --reuid=1000 --regid=1000 --clear-groups python3 /app/out/derive_report.py --data /app/data --out /app/out > /w/mrun_$n.txt 2>&1
  bash /tests/test.sh > /w/mtest_$n.txt 2>&1
  python3 - $n <<'PY'
import json,sys
d=json.load(open('/logs/verifier/reward-details.json'))
c=d['reward']['components'][0]['detail']['criteria']
pos=sum(x['weight'] for x in c if x['weight']>0)
got=sum(x['weight']*x['value'] for x in c)
fail=[x['name'] for x in c if x['weight']>0 and x['value']<1]
neg=[x['name'] for x in c if x['weight']<0 and x['value']>0]
print('MUT',sys.argv[1],'%g/%g'%(got,pos),'pct %.1f'%(100*got/pos),'failed',len(fail),' '.join(fail),'NEG',' '.join(neg),flush=True)
PY
done
echo ALL_DONE
