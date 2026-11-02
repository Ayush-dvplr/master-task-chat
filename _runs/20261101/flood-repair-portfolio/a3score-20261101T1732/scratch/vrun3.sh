#!/bin/bash
# inside a3s_verif (built from exe_copy tests/Dockerfile): /tests (no judge.toml), /app (data + a3 out as left), /logs
set -u
cd /app
sha256sum /app/out/* | sed 's/^/PRE /'
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
    for c in crit: print('CRIT', c['name'], c['weight'], c['value'])
PY
echo ALL_DONE
