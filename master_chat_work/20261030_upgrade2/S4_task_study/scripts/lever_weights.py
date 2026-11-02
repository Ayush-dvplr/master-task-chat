#!/usr/bin/env python3
"""Classify recorded lost checks by check name and judge metadata; no verifier run."""
import csv, json, pathlib, re, tomllib
R=pathlib.Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
O=pathlib.Path(__file__).resolve().parents[1]
tasks=list(csv.DictReader((O/'TASKS.csv').open()))
checks=list(csv.DictReader((O/'CHECKS.csv').open()))
bytask={}
for c in checks:
    if c['model']=='claude-opus-5': bytask.setdefault(c['id'],[]).append(c)

def family(n):
    n=n.lower()
    if re.search(r'time|runtime|completes|performance|scal',n) and re.search(r'time|runtime|completes|performance',n): return 'timeout_or_performance'
    if re.search(r'held.?out|hidden|unseen|fresh|eval_|_eval|^x\d\d_|^corpus_\d\d_|^scenario_|^slice_|^decoy_',n): return 'held_out_or_scenario_exact'
    if re.search(r'format|schema|vocab|key|byte|directory|relocat|cli|manifest|encoding|header|order|round|tie|boundary|missing|fallback|normalis',n): return 'convention_or_boundary'
    if re.search(r'exact|match|report|summary|ledger|rollup|spine|digest|totals|source|reconcil',n): return 'whole_output_exact'
    return 'other_behavior'

detail=[]
for t in tasks:
    if t['claude_opus_5_validity']!='valid' or float(t['claude_opus_5_final'])>=40:continue
    tid=t['id']; P=float(t['claude_opus_5_positive_weight'])
    for c in bytask[tid]:
        w=float(c['weight'])
        if w>0 and c['status']!='passed':
            detail.append({'id':tid,'channel':'test','check':c['name'],'family':family(c['name']),
                           'raw_lost_weight':w,'lost_final_points':50*w/P,'evidence':c['evidence']})
    sj=R/tid/'trajectories/claude-opus-5/run_1/verifier/score.json'
    s=json.loads(sj.read_text()); rub=s.get('rubric',[])
    criteria=tomllib.loads((R/tid/'tests/judge.toml').read_text()).get('criterion',[])
    JP=sum(float(x.get('score',0)) for x in rub if x.get('is_positive'))
    for i,x in enumerate(rub):
        if x.get('is_positive') and not x.get('passed'):
            target=(x.get('evaluation_target') or '').lower()
            cname=criteria[i].get('name','').lower() if i<len(criteria) else ''
            if target=='trajectory':
                fam='judge_probe' if re.search(r'probe|check|test|rerun|run_|recompute|compare|inspect|verify|validation',cname) else 'judge_other_trajectory'
            else: fam='judge_artifact_or_answer'
            detail.append({'id':tid,'channel':'judge','check':str(i+1),'family':fam,
                           'raw_lost_weight':x.get('score',0),'lost_final_points':50*float(x.get('score',0))/JP if JP else 0,
                           'evidence':str(sj)+f':$.rubric[{i}]'})
        elif not x.get('is_positive') and not x.get('passed'):
            detail.append({'id':tid,'channel':'judge','check':str(i+1),'family':'judge_negative_fired',
                           'raw_lost_weight':abs(float(x.get('score',0))),'lost_final_points':50*abs(float(x.get('score',0)))/JP if JP else 0,
                           'evidence':str(sj)+f':$.rubric[{i}]'})

with (O/'LEVER_DETAIL.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(detail)
families=sorted(set(x['family'] for x in detail)); total=sum(x['lost_final_points'] for x in detail)
rows=[]
for fam in families:
    dd=[x for x in detail if x['family']==fam]; pts=sum(x['lost_final_points'] for x in dd)
    rows.append({'family':fam,'lost_final_points':round(pts,2),'share_of_classified_loss_pct':round(100*pts/total,2),
                 'tasks_with_loss':len(set(x['id'] for x in dd)),'lost_checks_or_criteria':len(dd),
                 'task_count_denominator':len([t for t in tasks if t['claude_opus_5_validity']=='valid' and float(t['claude_opus_5_final'])<40]),
                 'classification':'INFERRED from check name / judge evaluation_target; see LEVER_DETAIL.csv'})
with (O/'LEVER_WEIGHTS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('low valid tasks',rows[0]['task_count_denominator'],'lost checks/criteria',len(detail),'total normalized lost final points',round(total,2))
for x in rows: print(x['family'],x['lost_final_points'],x['share_of_classified_loss_pct'],x['tasks_with_loss'])
