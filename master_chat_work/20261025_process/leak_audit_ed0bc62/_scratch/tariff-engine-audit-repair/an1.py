import json, re, io, csv, sys
from collections import Counter
src=open('test_output_copy.py').read().split('\n')
# slice lines 1-45 imports and 5630-5750 ledger
head='\n'.join(src[0:28]).replace('from rewardkit import criteria, criterion','')
led='\n'.join(src[5629:5746])
ns={}
exec(head+'\n'+led, ns)
Ledger=ns['_Ledger']
card=open('ci/rate_card.json').read()
def case_texts(case):
    meters="".join(f"{case['account']},{m['meter']},{m['active_from']},{m['active_to']}\n" for m in case['meters'])
    p=case['period']
    return {"meter_reads.jsonl":"".join(json.dumps(r)+"\n" for r in case['reads']),
     "accounts.csv":"account,meter,active_from,active_to\n"+meters,
     "billing_periods.csv":"account,start,end,plan,commitment,allowance\n"+f"{case['account']},{p['start']},{p['end']},{case['plan']},{case['commitment']},{case['allowance']}\n",
     "rate_card.json":card}
n=0;match=0;buggy_match=0;diffs=[]
cases=[json.loads(l) for l in open('ci/regression_cases.jsonl')]
res={}
for c in cases:
    t=Ledger(case_texts(c)).document()['invoices'][0]['total']
    res[c['name']]=t
    n+=1
    if t==c['customer_claim']: match+=1
    if c['disputed_total']==t: buggy_match+=1
print(n,'claim==oracle',match,'disputed==oracle',buggy_match)
# which are the claims otherwise?
log=open('ci/failing_tests.log').read()
st=dict(re.findall(r'test_(dispute_\d+) \(.*?\) \.\.\. (\w+)',log))
print(Counter(st.values()))
# compare ok/fail to claim==oracle
cm=Counter()
for c in cases:
    cm[(st[c['name']], res[c['name']]==c['customer_claim'], c['disputed_total']==c['customer_claim'])]+=1
print(cm)
# parse AssertionError a != b : a=buggy actual, b=claim
fails=re.findall(r"FAIL: test_(dispute_\d+).*?AssertionError: '([^']*)' != '([^']*)'",log,re.S)
print(len(fails))
agree=sum(1 for n_,a,b in fails if res[n_]==b); print('log expected(claim)==oracle',agree,'of',len(fails))
agree2=sum(1 for n_,a,b in fails if res[n_]==a); print('log actual==oracle',agree2)
json.dump(res,open('oracle_totals.json','w'))
# fields in cases
print(Counter(tuple(sorted(c.keys())) for c in cases))
