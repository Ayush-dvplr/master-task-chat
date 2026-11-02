import json, sys
O='out/'; L=lambda f: json.load(open(O+f))
S=L('summary.json'); Q=L('data_quality.json'); A=L('policy_audit.json')
print('summary keys', list(S)); print('rounds', len(S['rounds']), 'planned', S['planned_rounds'], 'rejected', S['rejected_rounds'])
rs=S['rounds']
assert [r['round'] for r in rs]==sorted(r['round'] for r in rs)
assert S['planned_rounds']==sum(r['status']=='planned' for r in rs)
assert S['rejected_rounds']==sum(r['status']=='rejected' for r in rs)
assert S['selected_proposals']==sum(len(r['selected']) for r in rs)
assert S['total_benefit']==sum(r['total_benefit'] for r in rs)
assert all(r['selected']==sorted(r['selected']) for r in rs)
assert all(r['selected']==[] and r['total_benefit']==0 for r in rs if r['status']=='rejected')
print('summary totals OK; selected', S['selected_proposals'], 'total_benefit', S['total_benefit'])
assert Q['planned_rounds']==S['planned_rounds'] and Q['rejected_rounds']==len(Q['rejected'])
print('rejected', [(x['round'],x['code'],x['file'],x['row']) for x in Q['rejected']])
print('conflicts', Q['conflict_pairs'], Q['conflicts_by_source'], 'withdrawn', Q['withdrawn_permit_rows'])
nonempty=sum(1 for l in open('environment/data/audit_queries.txt') if l.strip())
print('audit rows', len(A['rows']), 'nonempty lines', nonempty); assert len(A['rows'])==nonempty
from collections import Counter
print('audit kinds/status', Counter((r['kind'],r['status'],len(r)) for r in A['rows']))
# PAIR rows: conflicting pair never both selected
bad=[r for r in A['rows'] if r.get('conflict') and r['first_selected'] and r['second_selected']]
print('PAIR conflict both selected:', len(bad))
sel={r['round']:set(r['selected']) for r in rs}
assert all(r['selected']==(r['proposal'] in sel[r['round']]) for r in A['rows'] if r['status']=='planned' and r['kind']=='VALUE')
assert all(r['benefit']==r['households']*(r['segment_rate']+r['risk_uplift'])+r['premium'] for r in A['rows'] if 'benefit' in r)
tot=0; cnt=0
for reg in ['North','South','West','East']:
    d=L('region_%s.json'%reg); assert list(d)==['book','region','rounds','selected_proposals','total_benefit']
    assert d['total_benefit']==sum(x['benefit'] for x in d['rounds']) and d['selected_proposals']==sum(len(x['selected']) for x in d['rounds'])
    assert len(d['rounds'])==S['planned_rounds']; tot+=d['total_benefit']; cnt+=d['selected_proposals']
print('regions sum', tot, cnt, 'vs summary', S['total_benefit'], S['selected_proposals'])
for seg in ['commercial','public']:
    d=L('segment_%s.json'%seg); assert list(d)==['book','segment','rounds','selected_proposals','total_benefit']
    assert d['total_benefit']==sum(x['benefit'] for x in d['rounds'])
    print(seg, d['selected_proposals'], d['total_benefit'])
print('book', S['book'], Q['book'], A['book'])
