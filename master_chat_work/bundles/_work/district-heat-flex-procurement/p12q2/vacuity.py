"""Vacuity probe for the QL2 checks (host, test logic only, no solver run): for the new
bid_cost_rows / compliance_rows families and the narrowed shipped quality_counts projection,
a wrong-but-plausible output (zeros, the shipped figures on other inputs, +1 drift) must not project equal."""
import copy
import importlib.util
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "district-heat-flex-procurement"
sys.path.insert(0, str(WORK / "stub"))
spec = importlib.util.spec_from_file_location("tq", BUNDLE / "tests/test_output.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

roots = {"shipped": m.visible_root(), "H1": m.hidden_root("H1")}
for k in range(4):
    roots[f"wide{k}"] = m.wide_root(k)[0]
exp = {n: m.expected(r) for n, r in roots.items()}
ok = True


def zero(files, key):
    f = copy.deepcopy(files)
    for name, doc in f.items():
        if name.startswith("region_"):
            for e in doc["events"]:
                e[key] = 0 if key == "bid_cost_cents" else {k: 0 for k in e[key]}
    return f


for n, files in exp.items():
    for fam, key in (("bid_cost_rows", "bid_cost_cents"), ("compliance_rows", "compliance_counts")):
        right = m._project(fam, files)
        nonempty = bool(right)
        z = m._project(fam, zero(files, key)) != right
        other = m._project(fam, exp["shipped"]) != right if n != "shipped" else True
        print(f"{n:8s} {fam:16s} nonempty={nonempty} zeros_fail={z} shipped_copy_fail={other}")
        ok &= nonempty and z and other
f = copy.deepcopy(exp["shipped"])
f["data_quality.json"]["unallocated_pool_count"] += 1
qc = m._project("quality_counts", f, True) == m._project("quality_counts", exp["shipped"], True)
res = m._project("residual", f) != m._project("residual", exp["shipped"])
print(f"shipped unallocated_pool_count+1: quality_counts(shipped) unchanged={qc} residual fails={res}")
ok &= qc and res
print("VACUITY OK" if ok else "VACUITY FAIL")
