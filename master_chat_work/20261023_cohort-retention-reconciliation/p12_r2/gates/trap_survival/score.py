import sys, types, json, subprocess, tempfile, importlib.util, re, shutil
from pathlib import Path
reg={}
class _C:
    def __getattr__(self,n):
        def f(weight): reg[n]=weight
        return f
rk=types.ModuleType('rewardkit'); rk.criteria=_C(); rk.criterion=lambda **k:(lambda f:f)
sys.modules['rewardkit']=rk
spec=importlib.util.spec_from_file_location('t',sys.argv[1]); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
prog=Path(sys.argv[2])
base=Path(tempfile.mkdtemp()); out=base/'out'; out.mkdir()
shutil.copy(prog,out/'derive_report.py')
t.OUT=out; t.SCRIPT=out/'derive_report.py'; t.CORPUS=base/'corpus_absent'
data=base/'data'; data.mkdir()
for n,x in t._shipped_texts().items(): (data/n).write_text(x)
subprocess.run([sys.executable,str(t.SCRIPT),str(data),str(out)],capture_output=True)
earned=0; pos=sum(w for w in reg.values() if w>0); rows=[]
import io, contextlib
for n,w in reg.items():
    err=io.StringIO()
    with contextlib.redirect_stderr(err):
        v=getattr(t,n)(base)
    earned+=v*w; rows.append((n,w,round(v,3)))
for r in rows: print(*r, sep='\t')
print('SCORE', round(earned/pos,4), earned, pos)
