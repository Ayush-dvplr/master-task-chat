import json, sys, tempfile
from pathlib import Path
sys.argv=[sys.argv[0], sys.argv[1]]
exec(open("identity.py").read().split("specs = [")[0])
r=Path(tempfile.mkdtemp()); new.build(r, 91019, 0.05, "conv", {"hr":"zone:Site/Dune","start":"requested","window":"half"})
a=old.everything(r, {"hr":"zone:Site/Dune","start":"requested"}); b=new.everything(r, {"hr":"zone:Site/Dune","start":"requested","window":"half"})
print(type(a), len(a) if hasattr(a,'__len__') else '')
for i,(x,y) in enumerate(zip(a,b)):
    if json.dumps(x,sort_keys=True,default=str)!=json.dumps(y,sort_keys=True,default=str):
        print("part",i,type(x))
        if isinstance(x,dict):
            for k in x:
                if json.dumps(x.get(k),sort_keys=True,default=str)!=json.dumps(y.get(k),sort_keys=True,default=str): print("  key",k, str(x.get(k))[:200], "|", str(y.get(k))[:200])
