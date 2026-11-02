import csv,json,re,sys,datetime as dt
D=sys.argv[1]
reg={r['tail']:r for r in csv.DictReader(open(D+'/fleet_register.csv'))}
types=json.load(open(D+'/check_types.json'))
pub={r['request_id'] for r in csv.DictReader(open(D+'/published_plan.csv'))}
print('register cols',list(next(iter(reg.values())).keys()))
B={'North','South','West','East'}
def okd(s):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s): return False
    try: dt.date.fromisoformat(s); return True
    except: return False
seen=set();multi=0;n=0
for i,r in enumerate(csv.DictReader(open(D+'/check_requests.csv')),start=2):
    if r['season']!='2027A' or r['status']!='OPEN': continue
    n+=1;f=[]
    if r['request_id'] in seen: f.append('dup')
    seen.add(r['request_id'])
    if r['base'] not in B: f.append('base')
    if r['check_type'] not in types: f.append('type')
    t=reg.get(r['tail'])
    if t is None: f.append('tail')
    elif any(v=='RETIRED' for v in t.values()): f.append('retired')
    if not(okd(r['available_from']) and okd(r['due_date'])): f.append('date')
    if not re.fullmatch(r'[1-9]\d*',r['duration_days']): f.append('dur')
    if r['request_id'] not in pub: f.append('nopub')
    if f: print(i,r['request_id'],f)
    if len(f)>1: multi+=1
print('read rows',n,'multi-fault rows',multi)
