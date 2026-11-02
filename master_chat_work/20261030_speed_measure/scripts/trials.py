import json,csv,os,re
from datetime import datetime,timedelta,timezone
IST=timezone(timedelta(hours=5,minutes=30))
def P(s):
    if not s: return None
    z=s.endswith('Z'); s=s.rstrip('Z')
    d=datetime.fromisoformat(s)
    if z: d=d.replace(tzinfo=timezone.utc).astimezone(IST)
    else: d=d.replace(tzinfo=IST)
    return d
def dur(x):
    if not x: return None
    a,b=P(x.get('started_at')),P(x.get('finished_at'))
    return round((b-a).total_seconds(),1) if a and b else None
rows=[];cnt=0
for f in open('/tmp/_results.lst').read().split('\n'):
    if not f: continue
    ap=os.path.join('/Users/mac/Desktop/Terminal Bench',f) if f.startswith('./') else f
    try: d=json.load(open(ap))
    except Exception: continue
    if not isinstance(d,dict) or 'agent_execution' not in d or 'trial_name' not in d: continue
    st=P(d.get('started_at'))
    if not st or st< datetime(2026,10,26,tzinfo=IST): continue
    cfg=d.get('config',{}); ag=(cfg.get('agent') or {}).get('name') or (d.get('agent_info') or {}).get('name')
    rew=((d.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    ei=d.get('exception_info')
    rows.append([ap.replace('/Users/mac/Desktop/Terminal Bench/',''),d['task_name'].split('/')[-1],ag,(d.get('agent_info') or {}).get('model_info') and (d['agent_info']['model_info'] or {}).get('name'),st.strftime('%Y-%m-%d %H:%M:%S'),dur(d),dur(d.get('environment_setup')),dur(d.get('agent_setup')),dur(d.get('agent_execution')),dur(d.get('verifier')),rew,(ei or {}).get('exception_type') if ei else ''])
rows.sort(key=lambda r:r[4])
csv.writer(open('harbor_trial_phases.csv','w')).writerows([['path','task','agent','model','started_ist','total_s','env_setup_s','agent_setup_s','agent_exec_s','verifier_s','reward','exception']]+rows)
print(len(rows))
