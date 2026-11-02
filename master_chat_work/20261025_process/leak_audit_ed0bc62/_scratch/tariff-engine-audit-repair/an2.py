import json
from datetime import date
from collections import Counter
exec(open('an1.py').read().split("n=0;match=0")[0])
cases=[json.loads(l) for l in open('ci/regression_cases.jsonl')]
res=json.load(open('oracle_totals.json'))
strata=Counter(); ok=Counter()
for c in cases:
    t=res[c['name']]
    cl=c['customer_claim']
    # features
    p=c['period']; s=date.fromisoformat(p['start']); e=date.fromisoformat(p['end'])
    cross=(s.year,s.month)!=(e.year,e.month)
    nm=len(c['meters'])
    al=float(c['allowance'])>0
    nreads=len(c['reads'])
    for k in [('cross',cross),('multi',nm>1),('allow',al),('cross&multi&allow',(cross,nm>1,al))]:
        strata[k]+=1; ok[k]+= (t==cl)
for k in sorted(strata,key=str): print(k,strata[k],ok[k],round(ok[k]/strata[k],3))
# how do claims differ from oracle: delta distribution
d=Counter()
for c in cases:
    t=res[c['name']];cl=c['customer_claim']
    if t!=cl:
        d[round(float(cl)-float(t),2)]+=1
print(d.most_common(15))
