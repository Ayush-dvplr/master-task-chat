import json,sys,collections
recs=[json.loads(l) for l in open(sys.argv[1])]
L=["oracle","A","B","C","H7","agent_p3","agent_p2"]
err=[r['id'] for r in recs if 'error' in r]
print('corpora',len(recs),'errors',len(err),err[:5])
ok=[r for r in recs if 'error' not in r]
def dif(r,lab):
    x=r[lab]
    if x['code']!=0: return None
    return {a for a,h in x['h'].items() if h!=r['ref'][a]}
for lab in L:
    n=sum(1 for r in ok if dif(r,lab) is None or dif(r,lab))
    crash=sum(1 for r in ok if r[lab]['code']!=0)
    print(f"{lab:9s} differs from ref on {n}/{len(ok)} ({100*n/len(ok):.1f}%) crashes {crash}")
# per lever: corpora where mutant differs (separating), and agent behavior there
for lev in ["A","B","C","H7"]:
    sep=[r for r in ok if dif(r,lev)]
    for ag in ["agent_p3","agent_p2"]:
        agree_mut=sum(1 for r in sep if r[ag]['code']==0 and all(r[ag]['h'][a]==r[lev]['h'][a] for a in dif(r,lev)))
        agree_ref=sum(1 for r in sep if r[ag]['code']==0 and all(r[ag]['h'][a]==r['ref'][a] for a in dif(r,lev)))
        print(f"lever {lev}: separating {len(sep)}/{len(ok)} ({100*len(sep)/len(ok):.1f}%); {ag} matches mutant on lever artifacts {agree_mut} ({100*agree_mut/max(1,len(sep)):.1f}%), matches ref {agree_ref}")
# by fixset for H7
by=collections.Counter(); byd=collections.Counter()
for r in ok:
    k='+'.join(r['fix']) or 'none'; by[k]+=1
    if dif(r,'H7'): byd[k]+=1
print('H7 separating by fixset', {k:f"{byd[k]}/{by[k]}" for k in by})
arts=collections.Counter()
for r in ok:
    d=dif(r,'agent_p3')
    if d: arts.update(d)
print('agent_p3 differing artifacts', arts.most_common())
