import csv,json,pathlib
O=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_test_design_study')
rows=list(csv.DictReader((O/'inventory.csv').open()));m=json.loads((O/'scratch/metrics.json').read_text());sel=json.loads((O/'scratch/selection.json').read_text())
assert len(rows)==110 and len({r['id'] for r in rows})==110
assert len(sel['selected'])==25 and len(list((O/'cards').glob('*.md')))==25
assert set(p.stem for p in (O/'cards').glob('*.md'))==set(sel['selected'])
for p in (O/'cards').glob('*.md'):assert len(p.read_text().splitlines())<=80,p
for name,limit in [('PATTERNS.md',200),('FIX_PLAN.md',150),('REPORT.md',60)]:assert len((O/name).read_text().splitlines())<=limit,name
result={'sha':'191d357','slug':'_study','step':'test-design-study','status':'PARTIAL','tasks_scanned':len(rows),'deep_reads':len(sel['selected']),'patterns':len(m['patterns']),'hypothesis_r0':'confirmed','timeout_tasks':len(m['verified_timeout_task_ids']),'fix_plan':{'slipway':'Await a4; test oracle-safe scale only if crosswalk tier fails','hangar':'Implement nine legal Word carrier variants with independent views','flood':'Prototype bounded runtime gap; otherwise park','depot':'Park unless 120-second runtime gap is proved'},'report':str(O/'REPORT.md')}
(O/'result_191d357.json').write_text(json.dumps(result,indent=2)+'\n')
assert json.loads((O/'result_191d357.json').read_text())==result
print('verified',len(rows),'tasks',len(sel['selected']),'cards',len(m['patterns']),'patterns','omitted',len(sel['omitted']))
for name,v in m['patterns'].items():print(name,v['test_points_lost_sum'])
