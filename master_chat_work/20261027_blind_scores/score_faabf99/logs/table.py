import json,sys,glob,re
name=sys.argv[1]
t=glob.glob(f'/tmp/score_faabf99/jobs/faabf99-{name}/district-heat-flex-procurement__*/')[0]
d=json.load(open(t+'verifier/reward-details.json'))
crit=d['reward']['components'][0]['detail']['criteria']
msgs={}
for line in open(t+'verifier/test-stdout.txt'):
    if line.startswith('[check] '):
        j=json.loads(line[8:]); msgs[j['check']]=j['message']
LEV={f'wide_{k}_{s}' for k in (0,1) for s in ('portfolios_feasible','selection_match','tie_decisions_match','intervals_match')}
pos=sum(c['weight'] for c in crit if c['weight']>0)
earned=sum(c['weight']*c['value'] for c in crit if c['weight']>0)
neg=sum(-c['weight'] for c in crit if c['weight']<0 and c['value']>0)
print(f"| check | weight | lever | result | failure kind | first assertion line |\n|---|---|---|---|---|---|")
ll=nl=0;lp=0;kinds=set()
for c in crit:
    w=c['weight'];v=c['value'];n=c['name']
    if w<0: res='not fired' if v==0 else 'FIRED'; ok=v==0
    else: res='pass' if v==1 else 'FAIL'; ok=v==1
    m=msgs.get(n,'')
    kind=''
    if not ok:
        kind='TIMEOUT' if 'timed out' in m else ('CRASH' if 'exited with code' in m or 'Traceback' in m else ('MISSING' if 'missing' in m.lower() else 'WRONG'))
        if n in LEV: ll+=1; lp+=w; kinds.add(kind)
        elif w>0: nl+=1
    print(f"| {n} | {w:g} | {'yes' if n in LEV else ''} | {res} | {kind} | {m if not ok else ''} |")
print(f"\nearned={earned:g} neg_fired={neg:g} pos_total={pos:g} tests_pct={(earned-neg)/pos*100:.2f} lever_lost={ll}/8 lever_pts_lost={lp:g}/32 non_lever_lost={nl} kinds={sorted(kinds)}")
