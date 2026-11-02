import json, sys, time
from collections import Counter
sys.path.insert(0, "/h"); from load_t import load
from pathlib import Path
import os; t = load(os.environ.get("REF", "/tests/test_output.py"))
t0 = time.time()
cfg, prof, audit, summ = t._expected_shipped()
print("ref seconds", round(time.time()-t0,1))
A = Path("/a1out")
got = json.loads((A/"validation_report.json").read_text())
gs = json.loads((A/"summary.json").read_text())
for part in audit:
    e, g = audit[part], got.get(part)
    if part == "self_check":
        print("self_check equal", e == g); print(" exp", json.dumps(e, sort_keys=True)[:1500]); print(" got", json.dumps(g, sort_keys=True)[:1500]); continue
    es, gss = set(t._rows(e)), set(t._rows(g))
    print(part, "exp", len(es), "got", len(gss), "missing", len(es-gss), "extra", len(gss-es))
    for x in sorted(es-gss)[:6]: print("  MISSING", x[:300])
    for x in sorted(gss-es)[:6]: print("  EXTRA  ", x[:300])
def walk(a, b, p=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b: print(" summary key only one side", p+"/"+k, k in a, k in b); continue
            walk(a[k], b[k], p+"/"+k)
    elif a != b: print(" summary diff", p, "exp", str(a)[:200], "got", str(b)[:200])
walk(summ, gs)
