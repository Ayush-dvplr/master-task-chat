"""Replay the existing current-branch wrong-reading definitions on before/after tests."""
from pathlib import Path
import json, os, shutil, subprocess, sys
WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK))
import make_shipped as ms
import measure_variants as mv
from verify_visible import GROUPS,tree
BUNDLE=WORK.parent.parent/'schema-migration-plan-repair'
TRAP=WORK/'trap'
BLIND=Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/blind_r1')
ROOT=TRAP/'replay_scratch'
ROOT.mkdir(exist_ok=True)
ORACLE=ROOT/'oracle'
(ORACLE/'out').mkdir(parents=True,exist_ok=True)
for p in (BLIND/'out').iterdir():shutil.copy2(p,ORACLE/'out'/p.name)
BEFORE=TRAP/'before/tests/test_output.py'
AFTER=BUNDLE/'tests/test_output.py'
RUN=WORK/'run_checks.py'
variants=[*GROUPS,'F15 cli',*mv.INLINE]
results={}
for name in variants:
    src=ROOT/'tree';app=ROOT/'app'
    if src.exists():shutil.rmtree(src)
    if name in GROUPS or name=='F15 cli':tree(src,GROUPS.get(name,[16]))
    else:mv.inline(name,src)
    mv.package(src,ORACLE,app,add_main=name!='F15 cli')
    row={}
    for label,test_file in [('before',BEFORE),('after',AFTER)]:
        dest=TRAP/f'replay_{label}.json'
        env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TEST_OUTPUT_FILE=str(test_file))
        p=subprocess.run([sys.executable,str(RUN),str(app),str(dest)],env=env,capture_output=True,text=True,timeout=1200)
        if p.returncode or not dest.exists():
            row[label]={'error':p.stderr[-500:],'exit':p.returncode};continue
        d=json.loads(dest.read_text())
        row[label]={'earned':d['earned'],'positive':d['positive'],'loss':d['positive']-d['earned'],
                    'failed':[k for k,v in d['checks'].items() if v['weight']>0 and not v['pass']]}
    results[name]=row
    print(name,json.dumps({k:({t:v for t,v in r.items() if t!='failed'} if 'error' not in r else r) for k,r in row.items()}),flush=True)
    (TRAP/'variant_scores.json').write_text(json.dumps(results,indent=1))
    shutil.rmtree(src);shutil.rmtree(app)
print('ALL_DONE',flush=True)
