# local-improvement control: can 1 kWh move to a cheaper slot of the same bus
# (or to a cheaper slot of another bus via a swap) without breaking a cap?
import json,csv,collections
from datetime import datetime,timedelta
D='environment/data'
aud=json.load(open('out/policy_audit.json'))
types=json.load(open(D+'/bus_types.json'))
fr={r['vehicle_id']:r for r in csv.DictReader(open(D+'/fleet_register.csv'))}
first=datetime(2026,3,14,12,0); sm=15; ns=96
labels=[(first+timedelta(minutes=sm*s)).strftime('%Y-%m-%dT%H:%M') for s in range(ns)]
idx={l:i for i,l in enumerate(labels)}
bands=[(720,960,31),(960,1320,27),(1320,360,14),(360,720,22)]
def price(s):
    t=first+timedelta(minutes=sm*s); m=t.hour*60+t.minute
    for a,b,c in bands:
        if a<b:
            if a<=m<b: return c
        else:
            if m>=a or m<b: return c
ros={}
for r in csv.DictReader(open(D+'/roster.csv')):
    if r['plan_date']=='2026-03-14' and r['bus_id'] not in ros: ros[r['bus_id']]=r
dep=collections.defaultdict(lambda:[0]*ns); feeder=[0]*ns
x={}
for b in aud['buses']:
    for c in b['charges']:
        s=idx[c['slot']]; x[(b['bus_id'],s)]=c['kwh']
        dep[b['depot']][s]+=c['kwh']; feeder[s]+=c['kwh']
cab={'North':30,'South':30,'West':28,'East':35}
out1=[('North',2,datetime(2026,3,14,21,15),datetime(2026,3,14,22,30)),
      ('South',2,datetime(2026,3,15,2,0),datetime(2026,3,15,3,15))]
def dcap(d,s):
    t=first+timedelta(minutes=sm*s)
    o=sum(c for dd,c,a,z in out1 if dd==d and a<=t<z)
    return (cab[d]-o)*15
def fcap(s):
    t=first+timedelta(minutes=sm*s)
    return 170 if datetime(2026,3,14,20,0)<=t<datetime(2026,3,14,22,0) else 1300
imp=0
for b in aud['buses']:
    bid=b['bus_id']; d=b['depot']
    mx=types[fr[bid]['type']]['max_kwh_per_slot']
    a=datetime.fromisoformat(ros[bid]['arrive']); z=datetime.fromisoformat(ros[bid]['depart'])
    s0=int((a-first).total_seconds()//60//sm); s1=int((z-first).total_seconds()//60//sm)
    for s in range(s0,s1):
        if x.get((bid,s),0)<=0: continue
        for s2 in range(s0,s1):
            if s2==s: continue
            if price(s2)>=price(s): continue
            if x.get((bid,s2),0)+1>mx: continue
            if dep[d][s2]+1>dcap(d,s2): continue
            if feeder[s2]+1>fcap(s2): continue
            imp+=1
print('single-unit cheaper moves available:',imp)
