import subprocess, sys, json, os
from pathlib import Path
S = Path(sys.argv[1]); corp = [('shipped', Path(sys.argv[2]))] + [(n, S/'corp'/n) for n in ('h1','h2','h3','h4','h5','h6')]
vars_ = ['solve','v_finish','v_start','v_nodue','v_noclass','v_revid']
for name, d in corp:
    if not (d/'check_requests.csv').exists(): print(name, 'missing'); continue
    outs = {}
    for v in vars_:
        o = S/'vout'/name/v
        r = subprocess.run([sys.executable, str(S/'mut'/(v+'.py')), str(d), str(o)], capture_output=True, text=True, timeout=300)
        if r.returncode: print(name, v, 'rc', r.returncode, r.stderr[-300:]); continue
        outs[v] = {f: json.load(open(o/f)) for f in sorted(os.listdir(o)) if f.endswith('.json')}
    base = outs.get('solve')
    for v in vars_[1:]:
        if v not in outs: continue
        diff = [f for f in base if base[f] != outs[v].get(f)]
        print(name, v, 'DIFF' if diff else 'same', diff)
