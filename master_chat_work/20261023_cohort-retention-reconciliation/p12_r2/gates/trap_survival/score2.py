# score.py from harden_r2/gates plus per-check fault capture; usage: score2.py <test_output.py> <program> <out.json>
import sys, types, json, subprocess, tempfile, importlib.util, shutil, io, contextlib
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
earned=0; pos=sum(w for w in reg.values() if w>0); rows={}
for n,w in reg.items():
    err=io.StringIO()
    with contextlib.redirect_stderr(err):
        v=getattr(t,n)(base)
    earned+=v*w; rows[n]={"w":w,"v":round(v,4),"faults":err.getvalue()[:4000]}
json.dump({"score":round(earned/pos,4),"earned":round(earned,4),"pos":pos,"rows":rows},open(sys.argv[3],'w'),indent=1)
print(prog.name, Path(sys.argv[1]).name, 'SCORE', round(earned/pos,4), round(earned,4), pos)
