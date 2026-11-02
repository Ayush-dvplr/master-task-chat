import json, sys
sys.path.insert(0,'app'); import derive_report as d
o='out/'; L=lambda n: json.load(open(o+n))
s=L('summary.json'); q=L('data_quality.json'); a=L('policy_audit.json')
print('book',s['book'],'rounds',len(s['rounds']),'planned',s['planned_rounds'],'rejected',s['rejected_rounds'],'sel',s['selected_proposals'],'total',s['total_benefit'])
assert s['planned_rounds']+s['rejected_rounds']==len(s['rounds'])
assert s['selected_proposals']==sum(len(r['selected']) for r in s['rounds'])
assert s['total_benefit']==sum(r['total_benefit'] for r in s['rounds'])
assert [r['round'] for r in s['rounds']]==sorted(r['round'] for r in s['rounds'])
assert all(r['selected']==sorted(r['selected']) for r in s['rounds'])
assert len(q['rejected'])==s['rejected_rounds']
print('rejected', [(r['round'],r['code'],r['file'],r['row']) for r in q['rejected']])
print('dq', {k:q[k] for k in q if k not in('rejected',)})
nonempty=[i for i,l in enumerate(open('environment/data/audit_queries.txt').read().splitlines(),1) if l.split()]
assert [r['line'] for r in a['rows']]==nonempty; print('audit rows',len(a['rows']))
rs=0;rb=0
for reg in ['North','South','West','East']:
    x=L('region_%s.json'%reg); assert x['selected_proposals']==sum(len(r['selected']) for r in x['rounds']) and x['total_benefit']==sum(r['benefit'] for r in x['rounds']); assert len(x['rounds'])==s['planned_rounds']; rs+=x['selected_proposals']; rb+=x['total_benefit']
print('regions sum sel',rs,'benefit',rb,'(summary',s['selected_proposals'],s['total_benefit'],')')
for seg in ['commercial','public']:
    x=L('segment_%s.json'%seg); assert x['total_benefit']==sum(r['benefit'] for r in x['rounds']); print(seg,x['selected_proposals'],x['total_benefit'])
# verify selected portfolios feasible: no conflicting pair selected, shared crew cap
pa=[r for r in a['rows'] if r['kind']=='PAIR' and r['status']=='planned']
print('PAIR conflict&both selected:', sum(1 for r in pa if r['conflict'] and r['first_selected'] and r['second_selected']))
# compare DP vs B&B on rounds with n<=40
import time
cnt=0;mism=0;widths=[]
orig=d.solve_portfolio
def cmp(n,W,adj,cm,co):
    global cnt,mism
    order,bags,width=d.elimination_order(n,adj,cm); widths.append(width)
    r1=d.solve_dp(n,W,adj,cm,co,order,bags)
    if n<=40:
        saved=d.DP_MAX_WIDTH; d.DP_MAX_WIDTH=-1; r2=orig(n,W,adj,cm,co); d.DP_MAX_WIDTH=saved
        cnt+=1; mism+= r1!=r2
    return r1
d.solve_portfolio=cmp
sys.argv=['x','environment/data','work/probe_out']; d.main()
print('dp vs bnb compared',cnt,'mismatch',mism,'max width',max(widths))
