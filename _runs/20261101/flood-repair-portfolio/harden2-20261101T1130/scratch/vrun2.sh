#!/bin/bash
# inside cb8dada_verif: /tests (copy, no judge.toml), /app (data + out/derive_report.py), /logs
set -u
cd /app
s0=$(date +%s.%N)
timeout -s KILL 300 python3 -I -S /app/out/derive_report.py /app/data /app/out; echo "shipped_rc $?"
e0=$(date +%s.%N)
python3 -c "print('SHIPPED_SECONDS', round($e0-$s0,2))"
chown -R root:root /app; chmod -R a+rX /app
s=$(date +%s.%N)
mkdir -p /logs/verifier; bash /tests/test.sh > /logs/verifier/rk.out 2>&1; echo "rk_rc $?"
e=$(date +%s.%N)
python3 -c "print('VERIFIER_SECONDS', round($e-$s,2))"
python3 - <<'PY'
import json
d=json.load(open('/logs/verifier/reward.json'))
print('REWARD', json.dumps(d))
det=json.load(open('/logs/verifier/reward-details.json'))
for comp in det['reward']['components']:
    crit=comp['detail']['criteria']
    print('SCORE', comp['detail']['score'], 'FAILED', [c['name'] for c in crit if c['weight']>0 and c['value']<1], 'NEG_FIRED', [c['name'] for c in crit if c['weight']<0 and c['value']>0])
PY
echo ALL_DONE
