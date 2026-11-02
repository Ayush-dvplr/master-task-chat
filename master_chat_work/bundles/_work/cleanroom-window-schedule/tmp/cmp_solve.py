import json, sys, os, time, subprocess
sys.dont_write_bytecode=True
sys.path.insert(0, '.')
import datagen
B='../../cleanroom-window-schedule'
t=time.time()
r=subprocess.run([sys.executable,'-B',B+'/solution/solve.py',B+'/environment/data','tmp/out'],capture_output=True,text=True)
print('solve rc',r.returncode,r.stderr[-500:],'secs',round(time.time()-t,2))
files, attempts, nights, plans, ctx = datagen.build(datagen.specs(), datagen.SEED, 3000, 2600, datagen.THRESHOLDS, 60)
s=json.load(open('tmp/out/summary.json'))
got={n['night_id']:{p['job_id']:p['bay_id'] for p in n['plan']} for n in s['nights'] if n['status']=='accepted'}
bad=0;acc=0
for n,p in zip(nights,plans):
    if p is None:
        assert n['night_id'] not in got; continue
    acc+=1
    if got.get(n['night_id'])!=p: bad+=1; print('diff',n['night_id'])
print('accepted',acc,'diffs',bad, 'totals', s['totals'])
