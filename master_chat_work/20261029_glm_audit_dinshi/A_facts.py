#!/usr/bin/env python3
"""Read-only fact extraction for group A audit. Writes only to OUT with prefix A_."""
import json, os, sys, hashlib, glob, re
ROOT="/Users/mac/Desktop/Terminal Bench/anubis-stage-2"
OUT="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_glm_audit_dinshi"
TASKS=["072aced5-ac2b-5029-8831-e570547ce89a","56fe3bdd-00c6-5b13-a5c8-90a94ccc475e","8764bfdd-69b5-57a0-bc6a-db095fe071db","dad47963-3ef5-569b-9c83-dcf0fa4ffb57"]
MODELS=["glm-5.3","claude-opus-5"]
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()
def jl(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception as e: return {"_error":repr(e)}
def txt(p):
    try: return open(p,errors='replace').read()
    except Exception as e: return None
facts={}
for t in TASKS:
    for m in MODELS:
        rd=f"{ROOT}/{t}/trajectories/{m}/run_1"
        F={}
        F['pass_summary']=jl(f"{ROOT}/{t}/trajectories/{m}/pass_summary.json")
        cfg=jl(f"{rd}/config.json"); res=jl(f"{rd}/result.json")
        F['config']=cfg
        F['result']={k:res.get(k) for k in ['id','task_name','trial_name','task_checksum','agent_info','agent_result','verifier_result','verifier_environment_mode','exception_info','started_at','finished_at','environment_setup','agent_setup','agent_execution','verifier','step_results']}
        F['result_config_source_trial']=res.get('config',{}).get('source_trial')
        F['sha']={}
        for sub in ['config.json','result.json','report.json','trajectory_usage.json','agent/trajectory.json','verifier/ctrf.json','verifier/score.json','verifier/reward.json','verifier/reward_raw.json','verifier/reward.txt','verifier/reward-details.json','verifier/test-stdout.txt','artifacts/manifest.json']:
            p=f"{rd}/{sub}"
            F['sha'][sub]=(sha(p),os.path.getsize(p)) if os.path.exists(p) else None
        for sub in ['verifier/reward.json','verifier/reward_raw.json','verifier/reward.txt','verifier/test-stdout.txt','trajectory_usage.json']:
            F['raw_'+sub]=txt(f"{rd}/{sub}")
        # artifacts
        mf=jl(f"{rd}/artifacts/manifest.json")
        arts=[]
        if isinstance(mf,list):
            for e in mf:
                dest=f"{rd}/{e.get('destination')}"
                arts.append({'source':e['source'],'status':e['status'],'dest_exists':os.path.exists(dest),'size':os.path.getsize(dest) if os.path.isfile(dest) else None})
        F['manifest']=arts
        F['artifact_files']=sorted((os.path.relpath(p,rd),os.path.getsize(p)) for p in glob.glob(f"{rd}/artifacts/**/*",recursive=True) if os.path.isfile(p))
        # ctrf
        c=jl(f"{rd}/verifier/ctrf.json")
        try:
            r=c['results']; F['ctrf_summary']=r['summary']; F['ctrf_tests']=[{k:x.get(k) for k in ('name','status','duration','message','trace')} for x in r['tests']]
        except Exception as e: F['ctrf_summary']={'_error':repr(e)}
        # score
        sc=jl(f"{rd}/verifier/score.json")
        F['score_top']={k:v for k,v in sc.items() if k!='rubric'}
        F['rubric']=sc.get('rubric')
        rp=jl(f"{rd}/report.json")
        F['report_top']={k:v for k,v in rp.items() if k not in('rubric','pytest')}
        F['report_pytest']={k:v for k,v in rp.get('pytest',{}).items() if k!='tests'} if isinstance(rp.get('pytest'),dict) else None
        F['report_rubric_eq_score_rubric']= rp.get('rubric')==sc.get('rubric')
        # trajectory
        tr=jl(f"{rd}/agent/trajectory.json")
        steps=tr.get('steps',[])
        T={'n_steps':len(steps),'sources':{}, 'tool_calls':0,'tool_names':{},'empty_agent_steps':[],'first_ts':steps[0]['timestamp'] if steps else None,'last_ts':steps[-1]['timestamp'] if steps else None,'final_metrics':tr.get('final_metrics'),'schema':tr.get('schema_version')}
        errs={}
        gaps=[]
        from datetime import datetime
        prev=None
        for s in steps:
            T['sources'][s['source']]=T['sources'].get(s['source'],0)+1
            tcs=s.get('tool_calls') or []
            T['tool_calls']+=len(tcs)
            for tc in tcs: T['tool_names'][tc['function_name']]=T['tool_names'].get(tc['function_name'],0)+1
            if s['source']=='agent' and not tcs and not (s.get('message') or '').strip(): T['empty_agent_steps'].append(s['step_id'])
            ts=datetime.fromisoformat(s['timestamp'])
            if prev and (ts-prev).total_seconds()>120: gaps.append((s['step_id'],(ts-prev).total_seconds()))
            prev=ts
            obs=json.dumps(s.get('observation')) if s.get('observation') else ''
            for kw in ['Traceback','rate limit','RateLimit','context window','ContextWindow','BadRequest','APIError','Timeout','timed out','command not found','No such file','Permission denied','InternalServerError','overloaded','ServiceUnavailable']:
                if kw.lower() in (obs+(s.get('message') or '')).lower(): errs[kw]=errs.get(kw,0)+1
        T['gaps_gt120s']=gaps; T['error_kw']=errs
        if steps:
            T['duration_s']=(datetime.fromisoformat(steps[-1]['timestamp'])-datetime.fromisoformat(steps[0]['timestamp'])).total_seconds()
        last_msgs=[(s['step_id'],s['source'],s.get('message')) for s in steps if s['source']=='agent' and (s.get('message') or '').strip()]
        T['last_agent_msg']=last_msgs[-1] if last_msgs else None
        T['last_step']={k:(v if k!='observation' else str(v)[:800]) for k,v in (steps[-1] if steps else {}).items() if k!='tool_calls'}
        T['last_step_tool_calls']=str((steps[-1] if steps else {}).get('tool_calls'))[:600]
        T['extra_keys']=sorted({k for s in steps for k in s})
        F['traj']=T
        facts[f"{t}|{m}"]=F
json.dump(facts,open(f"{OUT}/A_facts.json",'w'),indent=1,default=str)
print("ok",len(facts))
