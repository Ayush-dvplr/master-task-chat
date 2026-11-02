"""seal.py <tests_dir> <solve.py> <corpus_dir> <out_dir>: run the module, print {digests, scalars} JSON."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rk  # noqa: E402

tests_dir, module, corpus, out = sys.argv[1:5]
T = rk.load(tests_dir)
os.makedirs(out, exist_ok=True)
env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/tmp", "PYTHONHASHSEED": "0",
       "PYTHONDONTWRITEBYTECODE": "1"}
mod_copy = Path(out).parent / ("mod_" + Path(out).name + ".py")
mod_copy.write_bytes(Path(module).read_bytes())
p = subprocess.run([sys.executable, "-I", "-B", str(mod_copy), "--data", corpus, "--out", out],
                   env=env, capture_output=True, text=True)
if p.returncode != 0:
    print(json.dumps({"error": p.returncode, "stderr": p.stderr[-2000:]}))
    sys.exit(1)
o = Path(out)
d = T._digests(o)
lines = []
for lob in T._LOBS:
    dev = json.loads((o / f"lob_{lob}.json").read_text()).get("chain_ladder_development", {})
    for c in ["H%02d" % i for i in range(1, 27)]:
        lines.append(f"{lob}|{c}|{dev.get(c, 0)}")
d["chain_ladder_development"] = T._digest(lines)
summ = json.loads((o / "summary.json").read_text())["totals"]
dq = json.loads((o / "data_quality.json").read_text())
tw = json.loads((o / "treaty_working.json").read_text())
sc = {}
for k in ("claims_admitted", "claims_dropped_late", "claims_retracted", "cross_source_collapsed",
          "total_alae", "total_ceded", "total_ibnr", "total_incurred", "total_paid_to_date",
          "total_ultimate", "unresolved_reinsurer"):
    sc[k] = summ[k]
for k, v in dq.items():
    sc["dq_" + k] = v
sc["treaty_ceded_total"] = tw["ceded_total"]
for k in ("retention", "working_excess", "cat_excess"):
    sc["treaty_" + k] = tw["layer_breakdown"][k]
ma = json.loads((o / "methodology_audit.json").read_text())
print(json.dumps({"digests": d, "scalars": sc, "audit": ma}, sort_keys=True))
