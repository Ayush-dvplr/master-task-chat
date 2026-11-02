import json,sys,collections
recs=[json.loads(l) for l in open(sys.argv[1])]
ok=[r for r in recs if 'error' not in r]
print('corpora',len(recs),'errors',len(recs)-len(ok),[r.get('error') for r in recs if 'error' in r][:3])
def dif(r,lab):
    x=r[lab]
    if x['code']!=0: return None
    return {a for a,h in x['h'].items() if h!=r['ref'][a]}
for lab in ["oracle","mut_N2","agent_p3"]:
    n=sum(1 for r in ok if dif(r,lab) is None or dif(r,lab))
    print(f"{lab} differs on {n}/{len(ok)} ({100*n/len(ok):.1f}%) crashes {sum(1 for r in ok if r[lab]['code']!=0)}")
sep=[r for r in ok if dif(r,'mut_N2')]
m=sum(1 for r in sep if r['agent_p3']['code']==0 and all(r['agent_p3']['h'][a]==r['mut_N2']['h'][a] for a in dif(r,'mut_N2')))
print(f"agent_p3 equals mut_N2 on its artifacts in {m}/{len(sep)} separating corpora")
by=collections.Counter();bd=collections.Counter()
for r in ok:
    k='+'.join(r['fix']) or 'none'; by[k]+=1; bd[k]+=bool(dif(r,'mut_N2'))
print('mut_N2 separating by fixset',{k:f"{bd[k]}/{by[k]}" for k in by})
notes=collections.Counter(r.get('fix_note','') for r in ok if r.get('fix_note'))
print('fix notes',notes.most_common(3))
small=min((r for r in sep), key=lambda r: len(dif(r,'mut_N2')))
print('smallest separating corpus',small['id'],small['seed'],small['fix'],sorted(dif(small,'mut_N2')))
