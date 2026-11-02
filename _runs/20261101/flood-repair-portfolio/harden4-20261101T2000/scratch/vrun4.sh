#!/bin/bash
# inside a3s_verif image: /tests0 (copy4 tests, ro), /data0 (shipped data, ro), /solution (ro), /progs (ro). env PROGS
set -u
for p in $PROGS; do
  echo "=== PROG $p"
  cd /; rm -rf /app /tests /logs; mkdir -p /app/out /logs/verifier; cp -r /data0 /app/data; cp -r /tests0 /tests
  s=$(date +%s.%N)
  if [ "$p" = oracle ]; then
    bash /solution/solve.sh > /tmp/solve_$p.out 2>&1; echo "solve_rc $?"; grep -E '^check|^rejected' /tmp/solve_$p.out
  elif [ "$p" = forkprobe ]; then
    cp /progs/$p.py /app/out/derive_report.py
  else
    cp /progs/$p.py /app/out/derive_report.py
    timeout 900 python3 /app/out/derive_report.py /app/data /app/out > /tmp/ship_$p.out 2>&1; echo "ship_rc $?"
  fi
  e=$(date +%s.%N); python3 -c "print('SHIPPED_RUN_SECONDS', round($e-$s,2))"
  chown -R root:root /app; chmod -R a+rX /app; cd /app
  s=$(date +%s.%N)
  bash /tests/test.sh > /tmp/rk_$p.out 2>&1; rc=$?; echo "rk_rc $rc"; [ $rc = 0 ] || tail -6 /tmp/rk_$p.out
  e=$(date +%s.%N)
  python3 -c "print('VERIFIER_SECONDS', round($e-$s,2))"
  python3 - <<'PY'
import os
hits=[]
for d in os.listdir('/proc'):
    if d.isdigit() and int(d)!=os.getpid():
        try: c=open('/proc/%s/cmdline'%d,'rb').read().replace(b'\0',b' ').decode()
        except OSError: continue
        if 'sleep 900' in c or 'derive_report' in c: hits.append((d,c))
print('SURVIVORS', len(hits), hits[:5])
PY
  python3 - <<'PY'
import json
try:
    d=json.load(open('/logs/verifier/reward.json')); print('REWARD', json.dumps(d))
    det=json.load(open('/logs/verifier/reward-details.json'))
    for comp in det['reward']['components']:
        crit=comp['detail']['criteria']
        tot=sum(c['weight'] for c in crit if c['weight']>0); got=sum(c['weight']*c['value'] for c in crit if c['weight']>0)
        print('SCORE', comp['detail']['score'], 'PTS %s/%s' % (round(got,2), tot), 'FAILED', [c['name'] for c in crit if c['weight']>0 and c['value']<1], 'NEG_FIRED', [c['name'] for c in crit if c['weight']<0 and c['value']>0])
except Exception as ex:
    print('PARSE_FAIL', ex)
PY
done
echo ALL_DONE
