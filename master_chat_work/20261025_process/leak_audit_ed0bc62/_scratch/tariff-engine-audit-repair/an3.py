import json
exec(open('an1.py').read().split("n=0;match=0")[0].replace("Ledger=ns['_Ledger']",""))
cases=[json.loads(l) for l in open('ci/regression_cases.jsonl')]
res=json.load(open('oracle_totals.json'))
base_src=head+'\n'+led
variants={
 'N3_per_meter': base_src.replace("            position += quantity\n","            pass\n"),
 'N1_one_pass': base_src.replace("        while left > 0 and live:\n            passes += 1","        while left > 0 and live and passes < 1:\n            passes += 1"),
 'N1_two_pass': base_src.replace("        while left > 0 and live:\n            passes += 1","        while left > 0 and live and passes < 2:\n            passes += 1"),
}
for name,s in variants.items():
    assert s!=base_src,name
    ns2={}; exec(s,ns2); L=ns2['_Ledger']
    diff=0; diff_claimmatch_oracle=0; diff_claimmatch_var=0
    for c in cases:
        t=L(case_texts(c)).document()['invoices'][0]['total']
        if t!=res[c['name']]:
            diff+=1
            diff_claimmatch_oracle+= c['customer_claim']==res[c['name']]
            diff_claimmatch_var+= c['customer_claim']==t
    print(name,'cases where variant differs from oracle',diff,'claim==oracle there',diff_claimmatch_oracle,'claim==variant',diff_claimmatch_var)
