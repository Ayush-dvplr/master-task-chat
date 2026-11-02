#!/usr/bin/env python3
"""Read-only extraction of the anubis-stage-2 task and recorded run inventory."""
import csv, json, os, pathlib, subprocess, tomllib, datetime

ROOT = pathlib.Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
OUT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_glm_audit_dinshi/AUDIT.md')
models = ('claude-opus-5','glm-5.3')
audit_verdict = {}
for line in AUDIT.read_text().splitlines():
    if line.startswith('| ') and ' | **' in line:
        cells = [x.strip() for x in line.split('|')]
        if len(cells)>4 and len(cells[1])==36:
            audit_verdict[cells[1]] = cells[4].strip('*')

def readjson(p):
    try: return json.loads(p.read_text())
    except (OSError, ValueError): return None

def date(s):
    return s[:10] if s else ''

# Commit dates and post-run change candidates, without reading sensitive trajectory content.
raw = subprocess.check_output(['git','-C',str(ROOT),'log','--format=COMMIT %H %aI %s','--name-only'],text=True)
commits=[]
for block in raw.split('COMMIT ')[1:]:
    lines=block.splitlines(); h,d,subject=lines[0].split(' ',2)
    files=[x for x in lines[1:] if x.strip()]
    commits.append((h,d,subject,files))
hist={}
for h,d,s,files in commits:
    for f in files:
        task=f.split('/')[0]
        if len(task)==36 and f.startswith(task+'/'):
            hist.setdefault(task,[]).append((h,d,s,f))

rows=[]; checks=[]
for taskfile in sorted(ROOT.glob('*/task.toml')):
    td=taskfile.parent; tid=td.name
    t=tomllib.loads(taskfile.read_text())
    j=tomllib.loads((td/'tests/judge.toml').read_text()) if (td/'tests/judge.toml').exists() else {}
    crit=j.get('criterion',[])
    rr={'id':tid,'authors':'; '.join(x.get('name','') for x in t.get('task',{}).get('authors',[])),
        'category':t.get('metadata',{}).get('category',''),
        'check_count':0,'positive_check_weight':0,'negative_check_weight':0,
        'verifier_timeout_sec':t.get('verifier',{}).get('timeout_sec',''),
        'judge_criteria_count':len(crit),'judge_positive_weight':sum(c.get('weight',0) for c in crit if c.get('weight',0)>0),
        'git_first_date':min((x[1] for x in hist.get(tid,[])),default='')[:10],
        'git_last_date':max((x[1] for x in hist.get(tid,[])),default='')[:10]}
    for model in models:
        base=td/'trajectories'/model
        ps=readjson(base/'pass_summary.json') or {}
        pr=(ps.get('per_run') or [{}])[0]
        vd=base/'run_1/verifier'
        ctrf=readjson(vd/'ctrf.json') or {}
        ts=ctrf.get('results',{}).get('tests',[])
        result=readjson(base/'run_1/result.json') or {}
        score=readjson(vd/'score.json') or {}
        reward=readjson(vd/'reward.json') or {}
        rw=reward.get('reward') if isinstance(reward,dict) else None
        score_final=score.get('final_reward') if isinstance(score,dict) else None
        reasons=[]
        if not pr: reasons.append('missing pass_summary per_run')
        if not ts: reasons.append('missing ctrf tests')
        if result.get('exception_info'): reasons.append('run exception_info')
        if any(x.get('status') not in ('passed','failed','skipped') for x in ts): reasons.append('nonstandard ctrf status')
        if isinstance(rw,(int,float)) and isinstance(score_final,(int,float)) and abs(rw-score_final)>1: reasons.append('reward/score mismatch')
        verdict='error-driven' if reasons else 'valid'
        if tid in audit_verdict and model=='glm-5.3':
            a=audit_verdict[tid]
            verdict='error-driven' if a.startswith('INVALID') else ('unclear' if a=='UNCLEAR' else 'valid')
            if a=='VALID-WITH-NOTES': reasons.append('prior audit valid with notes')
            if a=='UNCLEAR': reasons.append('prior audit unresolved cause')
            if a.startswith('INVALID'): reasons.append('prior audit verifier invalid')
        if not reasons and not (tid in audit_verdict and model=='glm-5.3') and pr.get('combined_score',100)<40 and len(ts) and all(x.get('status')=='failed' for x in ts):
            verdict='unclear'; reasons.append('all checks failed; cause unreviewed')
        prefix=model.replace('-','_').replace('.','_')
        rr.update({prefix+'_tests':pr.get('test_weights_percentage',''),prefix+'_rubric':pr.get('rubric_weights_percentage',''),
                   prefix+'_final':pr.get('combined_score',''),prefix+'_validity':verdict,
                   prefix+'_validity_reason':'; '.join(reasons),
                   prefix+'_evidence':str(base/'pass_summary.json')+':$.per_run[0]; '+str(vd/'ctrf.json')+':$.results',
                   prefix+'_run_started':date(result.get('started_at')),
                   prefix+'_check_count':len(ts),prefix+'_positive_weight':sum(x.get('weight',0) for x in ts if x.get('weight',0)>0),
                   prefix+'_negative_weight':sum(x.get('weight',0) for x in ts if x.get('weight',0)<0)})
        if model=='claude-opus-5':
            rr['check_count']=len(ts); rr['positive_check_weight']=rr[prefix+'_positive_weight'];rr['negative_check_weight']=rr[prefix+'_negative_weight']
        for x in ts:
            checks.append({'id':tid,'model':model,'name':x.get('name',''),'status':x.get('status',''),'weight':x.get('weight',0),
                           'evidence':str(vd/'ctrf.json')+':$.results.tests'})
    rows.append(rr)

with (OUT/'TASKS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (OUT/'CHECKS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(checks[0]));w.writeheader();w.writerows(checks)
with (OUT/'GIT_HISTORY.json').open('w') as f:
    json.dump({k:[{'commit':h,'date':d,'subject':s,'file':file} for h,d,s,file in v] for k,v in hist.items()},f,indent=1)
print('tasks',len(rows),'checks',len(checks),'commits',len(commits),'audit_reused',len(audit_verdict))
from collections import Counter
for model in models:
    p=model.replace('-','_').replace('.','_')
    print(model,Counter(r[p+'_validity'] for r in rows),'under40',sum(r[p+'_final']!='' and r[p+'_final']<40 for r in rows))
