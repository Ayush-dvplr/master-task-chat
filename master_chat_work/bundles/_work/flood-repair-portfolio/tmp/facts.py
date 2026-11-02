import importlib.util, sys, json
from pathlib import Path
sys.dont_write_bytecode=True
H=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(H))
import run_tests; run_tests.stub()
spec=importlib.util.spec_from_file_location("t",H.parent.parent/"flood-repair-portfolio/tests/test_output.py")
t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
sys.path.insert(0,str(H.parent.parent/"flood-repair-portfolio/solution")); import solve as S
for b in ["SHIPPED","H1","H2","H3","M"]:
    f=t.book_files(b); L=t._Ledger(f)
    import csv,io
    rec={}
    for r in csv.DictReader(io.StringIO(f["permits.csv"])): rec[r["round"]]=rec.get(r["round"],0)+1
    for e in json.loads(f["exclusions.json"]): rec[e["round"]]=rec.get(e["round"],0)+1
    for rid,rd in L.rounds.items():
        if rd.get("info") and len(rd["info"])>100:
            info=rd["info"]; pids=sorted(info); idx={p:i for i,p in enumerate(pids)}
            adj=[set() for _ in pids]
            for pr in rd["joined"]:
                a,b2=tuple(pr); adj[idx[a]].add(idx[b2]); adj[idx[b2]].add(idx[a])
            V=list(range(len(pids))); order=S.sweep_order(V, adj)
            pos={v:i for i,v in enumerate(order)}; last={v:max([pos[u] for u in adj[v]]+[pos[v]]) for v in order}
            wmax=max(sum(1 for u in order[:i+1] if last[u]>i) for i in range(len(order)))
            print(b,rid,len(pids),"pairs",len(rd["joined"]),"records",rec.get(rid),"deg",round(2*len(rd["joined"])/len(pids),2),"frontier",wmax)
