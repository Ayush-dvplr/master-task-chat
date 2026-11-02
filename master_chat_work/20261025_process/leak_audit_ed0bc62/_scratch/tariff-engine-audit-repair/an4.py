import json
exec(open('an1.py').read().split("n=0;match=0")[0].replace("Ledger=ns['_Ledger']",""))
exec(open('an3.py').read().split("for name,s in variants.items()")[0].split("res=json.load")[0].split("variants=")[0]) if False else None
base_src=head+'\n'+led
variants={
 'N3_per_meter': base_src.replace("            position += quantity\n","            pass\n"),
 'N1_one_pass': base_src.replace("        while left > 0 and live:\n            passes += 1","        while left > 0 and live and passes < 1:\n            passes += 1"),
 'N2_30day': base_src.replace("month_end.day","30"),
 'base': base_src}
texts={f:open('ci/'+f).read() for f in ["meter_reads.jsonl","accounts.csv","billing_periods.csv","rate_card.json"]}
docs={}
for n,s in variants.items():
    ns2={};exec(s,ns2); docs[n]=ns2['_Ledger'](texts).document()
b={i['account']:i for i in docs['base']['invoices']}
for n in docs:
    if n=='base':continue
    d=sum(1 for i in docs[n]['invoices'] if i!=b[i['account']])
    print(n,'accounts differing on shipped data:',d,'of',len(b))
# shipped months crossing?
import csv
from datetime import date
rows=list(csv.DictReader(open('ci/billing_periods.csv')))
print('crossing month periods',sum(1 for r in rows if r['start'][:7]!=r['end'][:7]),len(rows))
