from pathlib import Path
import json,os,shutil,subprocess,sys
W=Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair')
T=W/'trap';DATA=T/'probe/app/data';SOLVERS=W/'wrong/auditor_r1/solvers';ROOT=T/'archived_audit';ROOT.mkdir(exist_ok=True)
results={}
for path in sorted(SOLVERS.glob('*.py')):
 app=ROOT/path.stem/'app';shutil.copytree(DATA,app/'data',dirs_exist_ok=True)
 env=os.environ.copy();env.update(APP_ROOT=str(app),PYTHONDONTWRITEBYTECODE='1')
 try:
  p=subprocess.run([sys.executable,str(path)],env=env,text=True,capture_output=True,timeout=60)
  row={'exit':p.returncode,'stdout_tail':p.stdout[-200:],'stderr_tail':p.stderr[-300:],'outputs':sorted(q.name for q in (app/'out').glob('*'))}
 except subprocess.TimeoutExpired as exc:row={'timeout':60,'outputs':sorted(q.name for q in (app/'out').glob('*'))}
 results[path.stem]=row
 print(path.stem,json.dumps(row),flush=True)
 (T/'archived_audit.json').write_text(json.dumps(results,indent=1))
print('ALL_DONE',flush=True)
