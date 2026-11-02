#!/usr/bin/env python3
"""Read-only stage-2 Opus inventory and compact evidence for L5."""
import csv
import json
from pathlib import Path

ROOT = Path('/Users/mac/Desktop/Terminal Bench')
STAGE = ROOT / 'anubis-stage-2'
OUT = Path(__file__).resolve().parents[1]
S4 = ROOT / 'master_chat_work/20261030_upgrade2/S4_task_study/TASKS.csv'

def get(p):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None

def audit(row):
    uid = row['id']
    task = STAGE / uid
    base = task / 'trajectories/claude-opus-5'
    run = base / 'run_1'
    summ = get(base / 'pass_summary.json') or {}
    per = (summ.get('per_run') or [{}])[0]
    result = get(run / 'result.json') or {}
    score = get(run / 'verifier/score.json') or {}
    ctrf = get(run / 'verifier/ctrf.json') or {}
    reward = get(run / 'verifier/reward.json') or {}
    raw = get(run / 'verifier/reward_raw.json') or {}
    manifest = get(run / 'artifacts/manifest.json') or []
    tests = (ctrf.get('results') or {}).get('tests') or []
    summary = (ctrf.get('results') or {}).get('summary') or {}
    criteria = score.get('rubric') or []
    outputs = [m for m in manifest if m.get('source') == '/app/out' or m.get('source','').startswith('/app/out/')]
    bad = [m for m in outputs if m.get('status') != 'ok']
    final = per.get('combined_score')
    rwd = reward.get('reward')
    normalized = score.get('final_reward')
    checks = {
        'summary_score_agrees_reward': isinstance(final,(int,float)) and isinstance(rwd,(int,float)) and abs(final-rwd) <= .02,
        'score_json_agrees': normalized is None or (isinstance(final,(int,float)) and abs(final-normalized) <= .02),
        'raw_reward_agrees': not isinstance(raw.get('reward'),(int,float)) or (isinstance(final,(int,float)) and abs(final-100*raw['reward']) <= .02),
        'verifier_finished': bool((result.get('verifier') or {}).get('finished_at')),
        'no_result_exception': result.get('exception_info') is None,
        'test_results_present': bool(tests),
        'agent_output_captured': any(m.get('status') == 'ok' for m in outputs),
    }
    d = {
        'id':uid, 'category':row['category'], 'authors':row['authors'],
        'tests':per.get('test_weights_percentage'), 'rubric':per.get('rubric_weights_percentage'), 'final':final,
        'check_count':len(tests), 'judge_count':len(criteria), 'checks':checks,
        'reward':rwd, 'raw_reward':raw.get('reward'), 'score_final':normalized,
        'summary':summary, 'result_exception':result.get('exception_info'),
        'agent_execution':result.get('agent_execution'), 'verifier':result.get('verifier'),
        'outputs':outputs, 'missing_outputs':bad, 'failed_tests':[{'name':t.get('name'),'weight':t.get('weight'),'status':t.get('status')} for t in tests if t.get('status') != 'passed' and (t.get('weight') or 0)>0],
        'passed_tests':[{'name':t.get('name'),'weight':t.get('weight')} for t in tests if t.get('status') == 'passed' and (t.get('weight') or 0)>0],
        'failed_criteria':[{'number':c.get('number'),'criterion':c.get('criterion'),'score':c.get('score'),'target':c.get('evaluation_target'),'justification':c.get('justification')} for c in criteria if c.get('is_positive') and not c.get('passed')],
        'fired_negatives':[{'number':c.get('number'),'criterion':c.get('criterion'),'score':c.get('score'),'target':c.get('evaluation_target'),'justification':c.get('justification')} for c in criteria if not c.get('is_positive') and not c.get('passed')],
        'instruction':(task/'instruction.md').read_text(),
        'qc_files':[str(p.relative_to(task)) for p in task.rglob('*') if p.is_file() and 'qc' in p.name.lower()],
    }
    d['valid_recorded_run'] = all(checks.values())
    return d

def main():
    with S4.open(newline='') as f:
        rows = list(csv.DictReader(f))
    items = [audit(r) for r in rows]
    (OUT/'run_evidence.json').write_text(json.dumps(items,indent=2))
    valid = sorted((d for d in items if d['valid_recorded_run']), key=lambda d:d['final'])
    with (OUT/'BEST.csv').open('w',newline='') as f:
        w=csv.writer(f)
        w.writerow(['rank','id','category','tests','rubric','final','checks','judge_criteria','validity','evidence'])
        for i,d in enumerate(valid[:15],1):
            b=f"{STAGE/d['id']}/trajectories/claude-opus-5"
            w.writerow([i,d['id'],d['category'],d['tests'],d['rubric'],d['final'],d['check_count'],d['judge_count'],'valid_recorded_run',f'{b}/pass_summary.json:$.per_run[0]; {b}/run_1/verifier/reward.json:$.reward; {b}/run_1/verifier/ctrf.json:$.results; {b}/run_1/result.json:$.verifier; {b}/run_1/artifacts/manifest.json'])
    print('rows',len(items),'valid',len(valid),'top',[(x['id'][:8],x['final']) for x in valid[:15]])
    print('excluded',[(x['id'][:8],[k for k,v in x['checks'].items() if not v]) for x in items if not x['valid_recorded_run']])

if __name__ == '__main__':
    main()
