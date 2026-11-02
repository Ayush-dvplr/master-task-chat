import sys, json, shutil
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import test_output as T
root = Path(sys.argv[2]); root.mkdir(exist_ok=True)
for name in T.HIDDEN:
    d = root / name
    if d.exists(): shutil.rmtree(d)
    d.mkdir()
    seed, empty, stype, x1 = T.HIDDEN[name]
    inst, want = T._planted_corpus(name, seed, empty, stype, x1, d)
    print(name, 'draw', inst['meta'].get('draw'), 'deferred', sum(1 for r in want['policy_audit.json']['checks'] if r['decision']=='deferred'))
for name in ('m1','m2'):
    pass
