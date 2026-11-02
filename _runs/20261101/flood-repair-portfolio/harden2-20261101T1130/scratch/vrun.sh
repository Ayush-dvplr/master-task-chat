#!/bin/bash
# inside cb8dada_verif: /tests (copy, no judge.toml), /app (data + out/derive_report.py), /logs
set -u
cd /app
python3 -I -S /app/out/derive_report.py /app/data /app/out; echo "shipped_rc $?"
chown -R root:root /app; chmod -R a+rX /app
s=$(date +%s.%N)
mkdir -p /logs/verifier; bash /tests/test.sh > /logs/verifier/rk.out 2>&1; echo "rk_rc $?"
e=$(date +%s.%N)
python3 -c "print('VERIFIER_SECONDS', round($e-$s,2))"
cat /logs/verifier/reward.json; echo
python3 - <<'PY'
import json
d=json.load(open('/logs/verifier/reward-details.json')) if __import__('os').path.exists('/logs/verifier/reward-details.json') else {}
print(json.dumps(d)[:3000])
PY
echo ALL_DONE
