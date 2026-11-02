import json, os, csv, sys
from datetime import datetime, timedelta
D='environment/data'; O='out'
names=['policy_audit.json','region_North.json','region_South.json','region_West.json',
 'region_East.json','segment_commercial.json','segment_public.json','summary.json','data_quality.json']
miss=[n for n in names if not os.path.isfile(os.path.join(O,n))]
print('missing files:',miss)
J=lambda n: json.load(open(os.path.join(O,n)))
aud=J('policy_audit.json'); summ=J('summary.json'); dq=J('data_quality.json')
first=datetime(2026,3,14,12,0); sm=15; ns=96
labels=[(first+timedelta(minutes=sm*s)).strftime('%Y-%m-%dT%H:%M') for s in range(ns)]
# slot list lengths / order
for n in names[1:7]:
    d=J(n); ok=[x['slot'] for x in d['slots']]==labels
    print(n,'slots',len(d['slots']),'order_ok',ok)
print('summary feeder_kwh_by_slot',len(summ['feeder_kwh_by_slot']),
      'order_ok',[x['slot'] for x in summ['feeder_kwh_by_slot']]==labels)
# per-bus arithmetic
reg={}
for ln in open(os.path.join(D,'fleet_register.csv')):
    pass
types=json.load(open(os.path.join(D,'bus_types.json')))
fr={r['vehicle_id']:r for r in csv.DictReader(open(os.path.join(D,'fleet_register.csv')))}
bad=0; feeder=[0]*ns; dep={}; cls={}
tot_need=tot_del=0; wu=0; cost=0
bands=[(12*60,16*60,31),(16*60,22*60,27),(22*60,6*60,14),(6*60,12*60,22)]
def price(m):
    m%=1440
    for a,b,c in bands:
        if a<b:
            if a<=m<b: return c
        else:
            if m>=a or m<b: return c
print('bus count',len(aud['buses']),'sorted',[b['bus_id'] for b in aud['buses']]==sorted(b['bus_id'] for b in aud['buses']))
W={'public':4,'commercial':1}
for b in aud['buses']:
    s=sum(c['kwh'] for c in b['charges'])
    if s!=b['delivered_kwh'] or b['need_kwh']-b['delivered_kwh']!=b['unmet_kwh']: bad+=1
    if b['unmet_kwh']<0: bad+=1
    mx=types[fr[b['bus_id']]['type']]['max_kwh_per_slot']
    for c in b['charges']:
        if c['kwh']<1 or c['kwh']>mx: bad+=1
        si=labels.index(c['slot']); feeder[si]+=c['kwh']
        dep.setdefault(b['depot'],[0]*ns)[si]+=c['kwh']
        cls.setdefault(b['class'],[0]*ns)[si]+=c['kwh']
        cost+=c['kwh']*price((first+timedelta(minutes=sm*si)).hour*60+(first+timedelta(minutes=sm*si)).minute)
    slots=[c['slot'] for c in b['charges']]
    if slots!=sorted(slots): bad+=1
    tot_need+=b['need_kwh']; tot_del+=b['delivered_kwh']; wu+=W[b['class']]*b['unmet_kwh']
print('per-bus violations',bad,'need',tot_need,'delivered',tot_del)
print('weighted_unmet recomputed',wu,'summary',summ['weighted_unmet_kwh'])
print('cost recomputed',cost,'summary',summ['energy_cost_cents'])
print('feeder peak',max(feeder),'summary',summ['feeder_peak_kwh'])
print('feeder by slot match',[x['kwh'] for x in summ['feeder_kwh_by_slot']]==feeder)
# capacity limits
cab={'North':30,'South':30,'West':28,'East':35}
out1=[(d,c,datetime.fromisoformat(a),datetime.fromisoformat(z)) for d,c,a,z in
 [('North',2,'2026-03-14T21:15','2026-03-14T22:30'),('South',2,'2026-03-15T02:00','2026-03-15T03:15')]]
viol=[]
for s in range(ns):
    t=first+timedelta(minutes=sm*s)
    lim=170 if datetime(2026,3,14,20,0)<=t<datetime(2026,3,14,22,0) else 1300
    if feeder[s]>lim: viol.append(('feeder',labels[s],feeder[s],lim))
    for d,row in dep.items():
        o=sum(c for dd,c,a,z in out1 if dd==d and a<=t<z)
        cl=(cab[d]-o)*15
        if row[s]>cl: viol.append(('depot',d,labels[s],row[s],cl))
print('capacity violations',viol[:6],'count',len(viol))
# region/segment cross-check
for d in ['North','South','West','East']:
    r=J('region_%s.json'%d)
    e=sum(b['delivered_kwh'] for b in aud['buses'] if b['depot']==d)
    u=sum(b['unmet_kwh'] for b in aud['buses'] if b['depot']==d)
    n=sum(1 for b in aud['buses'] if b['depot']==d)
    sl=[x['kwh'] for x in r['slots']]==dep.get(d,[0]*ns)
    fk=[x['feeder_kwh'] for x in r['slots']]==feeder
    print('region',d,r['buses']==n,r['energy_kwh']==e,r['unmet_kwh']==u,'slots',sl,'feeder',fk,'cost',r['cost_cents'])
tc=0
for c in ['commercial','public']:
    g=J('segment_%s.json'%c)
    e=sum(b['delivered_kwh'] for b in aud['buses'] if b['class']==c)
    n=sum(1 for b in aud['buses'] if b['class']==c)
    u=sum(b['unmet_kwh'] for b in aud['buses'] if b['class']==c)
    print('segment',c,g['buses']==n,g['energy_kwh']==e,g['unmet_kwh']==u,
          'slots',[x['kwh'] for x in g['slots']]==cls.get(c,[0]*ns),'cost',g['cost_cents'])
    tc+=g['cost_cents']
print('segment cost sum',tc,'=?',summ['energy_cost_cents'],
      'region cost sum',sum(J('region_%s.json'%d)['cost_cents'] for d in ['North','South','West','East']))
print('buses_planned',summ['buses_planned']==len(aud['buses']),
      'buses_short',summ['buses_short']==sum(1 for b in aud['buses'] if b['unmet_kwh']>0),
      'buses_changed',summ['buses_changed']==sum(1 for b in aud['buses'] if b['changed']),
      'records_rejected',summ['records_rejected']==len(dq['rejected']))
# tier-1 bound: per-bus window cap
import collections
ros=list(csv.DictReader(open(os.path.join(D,'roster.csv'))))
win={}
for r in ros:
    if r['plan_date']!='2026-03-14': continue
    win.setdefault(r['bus_id'],(r['arrive'],r['depart']))
ub=0
for b in aud['buses']:
    a,z=win[b['bus_id']]
    s0=(datetime.fromisoformat(a)-first).total_seconds()//60//sm
    s1=(datetime.fromisoformat(z)-first).total_seconds()//60//sm
    mx=types[fr[b['bus_id']]['type']]['max_kwh_per_slot']
    cap=mx*int(s1-s0)
    ub+=W[b['class']]*max(0,b['need_kwh']-cap)
print('tier1 lower bound on weighted unmet (window only)',ub)
# published comparison
pub=collections.defaultdict(int)
nrows=0
for i,r in enumerate(csv.DictReader(open(os.path.join(D,'published_plan.csv')))):
    if r['plan_date']!='2026-03-14': continue
    nrows+=1; pub[(r['bus_id'],r['slot_start'])]+=int(r['kwh'])
plan=collections.defaultdict(int)
for b in aud['buses']:
    for c in b['charges']: plan[(b['bus_id'],c['slot'])]+=c['kwh']
rejpub=set()
moved=0; diff=0
for k,v in pub.items():
    if k in plan or True:
        pass
print('published plan-date rows',nrows,'published total',sum(pub.values()),'plan total',sum(plan.values()))
accepted_pub={k:v for k,v in pub.items()}
mv=0; ch=set()
for k,v in accepted_pub.items():
    bid=k[0]
    if bid not in {b['bus_id'] for b in aud['buses']}: continue
    d=v-plan.get(k,0)
    if d>0: mv+=d
    if d!=0: ch.add(bid)
print('moved (pub vs plan, accepted buses incl out-of-window rows)',mv,'changed buses',len(ch),'summary moved',summ['moved_kwh'])
print('data_quality rejected',dq['rejected'])
