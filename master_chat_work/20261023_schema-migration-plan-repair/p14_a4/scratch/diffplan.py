"""Dump plans of one migrakit build over small random in-limits graphs (agent's stress builder, small sizes)."""
import json, random, sys, importlib.util
from pathlib import Path
src, out, base = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, src)
spec = importlib.util.spec_from_file_location("s8", "stress8_local.py")
import migrakit
FIELDS = ["f%d" % i for i in range(10)]
# reuse build() from stress8_local without running its main: exec the def only
code = Path("stress8_local.py").read_text().split("def run(")[0]
ns = {"__name__": "x"}; exec(code, ns)
res = {}
for seed in range(400):
    r = random.Random(seed)
    n, par = r.randint(3, 8), r.randint(1, 3)
    folder = base / f"g{seed}"
    ns["build"](folder, n, par, seed, r.random() < 0.8)
    reg = migrakit.load_contracts(folder)
    pr = random.Random(seed + 7)
    for t in range(4):
        payload = {f: pr.choice([None, 1, "x"]) for f in FIELDS if pr.random() < 0.6}
        try:
            v = migrakit.plan_migration(reg, "d.v1", payload)
        except migrakit.MigrationError as e:
            v = "ERR:" + str(e.code)
        res[f"{seed}/{t}"] = v
Path(out).write_text(json.dumps(res))
