import sys,types,json,os,traceback
O=os.path.dirname(os.path.abspath(__file__)); T=sys.argv[1]
sys.path.insert(0,O+"/stub")
src=open(T+"/tests/test_output.py").read().replace("/tmp/h3_verifier_data",O+"/h3_verifier_data")
mod=types.ModuleType("h3t"); mod.__file__="h3t.py"; sys.modules["h3t"]=mod
exec(compile(src,"h3t","exec"),mod.__dict__)
from pathlib import Path
AO=Path(T+"/trajectories/claude-opus-5/run_1/artifacts/app/out")
mod.OUT_DIR=AO; mod.SCHEDULER=AO/"reusable_scheduler.py"; mod._run_agent.__defaults__=(AO/"reusable_scheduler.py",)
ref=mod._reference_solve(mod.DATA_DIR)
for n in mod.ALL_ARTIFACTS:
    a=json.loads((AO/n).read_text())
    r=ref.get(n)
    print(n,"MATCH" if a==r else "DIFF")
print("ref _total_cost",ref["_total_cost"],"_stream",ref["_stream_count"],"_epoch",ref["_epoch_count"])
fs=json.loads((AO/"final_state.json").read_text()); print("agent final",{k:fs[k] for k in fs if k!="folded_digest_sha256"})
tests=[k for k in dir(mod) if k.startswith("test_") and "negative" not in k]
for t in tests:
    try: getattr(mod,t)(); print("PASS",t)
    except Exception as e: print("FAIL",t,type(e).__name__,str(e)[:300])
json.dump({k:v for k,v in ref.items() if not k.startswith("_")},open(O+"/h3_ref.json","w"),sort_keys=True,indent=1)
