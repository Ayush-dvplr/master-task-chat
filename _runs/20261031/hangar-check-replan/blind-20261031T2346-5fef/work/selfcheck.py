import json, csv, datetime, collections, sys
D='environment/data/'; O='out/'
lim={}
for l in open(D+'fleet_limits.toml'):
    k,v=l.split('=');lim[k.strip()]=v.strip().strip('"')
s0=datetime.date.fromisoformat(lim['season_start']); s1=datetime.date.fromisoformat(lim['season_end'])
pool=int(lim['overtime_pool_shifts']); sc=int(lim['shift_cost'])
N=(s1-s0).days+1
rates={}
cur=None
for l in open(D+'class_rates.yaml'):
    if not l.strip(): continue
    k,v=l.split(':',1)
    if not l[0].isspace(): cur=k.strip(); rates[cur]={}
    else: rates[cur][k.strip()]=int(v)
ct=json.load(open(D+'check_types.json'))
reg={r['tail']:r for r in csv.DictReader(open(D+'fleet_register.csv'))}
pub={r['request_id']:r['published_start'] for r in csv.DictReader(open(D+'published_plan.csv'))}
reqs={}
for r in csv.DictReader(open(D+'check_requests.csv')):
    if r['season']==lim['season'] and r['status']=='OPEN' and r['request_id'] not in reqs:
        reqs[r['request_id']]=r
closed=collections.defaultdict(set); nostart=collections.defaultdict(set)
for l in open(D+'base_calendar.jsonl'):
    o=json.loads(l); d=datetime.date.fromisoformat(o['date'])
    if s0<=d<=s1:
        if o['status']=='CLOSED': closed[o['base']].add(d)
        elif o['status']=='NO_START': nostart[o['base']].add(d)
for b,f,t in [('East','2027-03-23','2027-03-31'),('South','2027-04-13','2027-04-21')]:
    a=datetime.date.fromisoformat(f); z=datetime.date.fromisoformat(t)
    while a<=z: closed[b].add(a); a+=datetime.timedelta(days=1)
revised={'VT-SUX':'2027-03-20','VT-GZE':'2027-05-16','VT-EZW':'2027-03-27','VT-CQR':'2027-06-27'}
plan=json.load(open(O+'check_plan.json'))
errs=[]
assert plan['season']==lim['season']
ids=[c['request_id'] for c in plan['checks']]
assert ids==sorted(ids), 'not sorted'
dq=json.load(open(O+'data_quality.json'))
rej={r['request_id'] for r in dq['rejected']}
expected=set(reqs)-{r['request_id'] for r in dq['rejected'] if r['reason']!='duplicate_request'}
# duplicate id appears once in rejected and once in plan
assert len(ids)==len(set(ids))==len(expected), (len(ids),len(expected))
assert set(ids)==expected
occ=collections.defaultdict(list)
tot=collections.Counter(); shifts_total=0
for c in plan['checks']:
    r=reqs[c['request_id']]; cls=reg[r['tail']]['aircraft_class']
    assert c['aircraft_class']==cls and c['tail']==r['tail'] and c['base']==r['base'] and c['check_type']==r['check_type']
    assert c['segment']==('public' if cls=='regional' else 'commercial')
    p=int(r['duration_days']); spec=ct[r['check_type']]
    av=datetime.date.fromisoformat(revised.get(r['tail'], r['available_from']))
    if av<s0: av=s0
    due=datetime.date.fromisoformat(r['due_date'])
    if c['decision']=='scheduled':
        st=datetime.date.fromisoformat(c['start_date']); fi=datetime.date.fromisoformat(c['finish_date'])
        dog=(fi-st).days+1
        if dog!=p-c['compress_days']: errs.append(('dog',c['request_id']))
        if not (0<=c['compress_days']<=min(spec['max_compress_days'],p-1)): errs.append(('compress',c['request_id']))
        if c['overtime_shifts']!=c['compress_days']*spec['overtime_shifts_per_day']: errs.append(('shifts',c['request_id']))
        if st<av: errs.append(('avail',c['request_id']))
        if fi>s1: errs.append(('seasonend',c['request_id']))
        if st in closed[r['base']] or st in nostart[r['base']]: errs.append(('startday',c['request_id']))
        d=st
        while d<=fi:
            if d in closed[r['base']]: errs.append(('spanclosed',c['request_id']))
            occ[r['base']].append((d,c['request_id'])); d+=datetime.timedelta(days=1)
        od=max(0,(fi-due).days)
        if c['overdue_days']!=od: errs.append(('overdue',c['request_id'],od))
        if c['moved']!=(c['start_date']!=pub[c['request_id']]): errs.append(('moved',c['request_id']))
        if c['deferral_reason'] is not None: errs.append(('defreason',c['request_id']))
        shifts_total+=c['overtime_shifts']
    else:
        if c['start_date'] is not None or c['finish_date'] is not None: errs.append(('nulls',c['request_id']))
        if not (c['compress_days']==c['overtime_shifts']==c['overdue_days']==0): errs.append(('zeros',c['request_id']))
        if c['moved']is not True: errs.append(('movedef',c['request_id']))
        # alone-on-line feasibility
        ok=False
        for cc in range(0,min(spec['max_compress_days'],p-1)+1):
            q=p-cc; d=av
            while d+datetime.timedelta(days=q-1)<=s1:
                if d not in closed[r['base']] and d not in nostart[r['base']] and not any(d+datetime.timedelta(days=i) in closed[r['base']] for i in range(q)):
                    ok=True;break
                d+=datetime.timedelta(days=1)
            if ok:break
        want='plan_trade' if ok else 'no_slot'
        if c['deferral_reason']!=want: errs.append(('reason',c['request_id'],c['deferral_reason'],want))
for b,v in occ.items():
    days=[d for d,_ in v]
    if len(days)!=len(set(days)): errs.append(('overlap',b))
if shifts_total>pool: errs.append(('pool',shifts_total))
# aggregate cross-check
def agg(sel):
    o=dict(checks_scheduled=0,checks_deferred=0,compress_days=0,overtime_shifts=0,overdue_days=0,overdue_cost=0,deferral_cost=0,revenue_lost=0,moved=0,first_start=None,last_finish=None)
    for c in sel:
        r=reqs[c['request_id']]; cls=reg[r['tail']]['aircraft_class']; rt=rates[cls]
        if c['moved']: o['moved']+=1
        if c['decision']=='scheduled':
            o['checks_scheduled']+=1; o['compress_days']+=c['compress_days']; o['overtime_shifts']+=c['overtime_shifts']
            o['overdue_days']+=c['overdue_days']; o['overdue_cost']+=c['overdue_days']*rt['overdue_weight']
            o['revenue_lost']+=(int(r['duration_days'])-c['compress_days'])*rt['revenue_per_day']
            if o['first_start'] is None or c['start_date']<o['first_start']: o['first_start']=c['start_date']
            if o['last_finish'] is None or c['finish_date']>o['last_finish']: o['last_finish']=c['finish_date']
        else:
            o['checks_deferred']+=1; o['deferral_cost']+=rt['deferral_penalty']
    return o
for b in ['North','South','West','East']:
    f=json.load(open(O+'regions/region_%s.json'%b.lower()))
    e=agg([c for c in plan['checks'] if c['base']==b]); e['fleet_overtime_used']=shifts_total
    if f!=dict({'base':b},**e): errs.append(('region',b,f,e))
for sg in ['commercial','public']:
    f=json.load(open(O+'segments/segment_%s.json'%sg))
    e=agg([c for c in plan['checks'] if c['segment']==sg]); e['fleet_overtime_used']=shifts_total
    if f!=dict({'segment':sg},**e): errs.append(('segment',sg,f,e))
fl=agg(plan['checks'])
sm=json.load(open(O+'plan_summary.json'))
exp_terms={'first':fl['overdue_cost']+fl['deferral_cost'],'second':fl['revenue_lost']+sc*shifts_total,'third':fl['moved']}
if sm['plan_terms']!=exp_terms: errs.append(('terms',sm['plan_terms'],exp_terms))
if sm['fleet_overtime_used']!=shifts_total: errs.append(('fou',))
if [sm['checks_scheduled'],sm['checks_deferred'],sm['moved']]!=[fl['checks_scheduled'],fl['checks_deferred'],fl['moved']]: errs.append(('fleetcounts',))
if [b['base'] for b in sm['bases']]!=['North','South','West','East']: errs.append(('baseorder',))
if [g['segment'] for g in sm['segments']]!=['commercial','public']: errs.append(('segorder',))
if set(dq['counts'])!={'duplicate_request','unknown_base','unknown_check_type','unknown_tail','retired_tail','bad_date','bad_duration','no_published_start'}: errs.append(('counts',))
if sum(dq['counts'].values())!=len(dq['rejected']): errs.append(('countsum',))
print('terms',exp_terms,'shifts',shifts_total,'/',pool,'sched',fl['checks_scheduled'],'def',fl['checks_deferred'],'moved',fl['moved'])
print('deferred:',[(c['request_id'],c['deferral_reason']) for c in plan['checks'] if c['decision']=='deferred'])
print('ERRORS:',errs if errs else 'none')
