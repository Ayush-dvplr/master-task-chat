import json, sys
from pathlib import Path
R = Path("/tmp/smpr-hard-20261021T1730/results")
oracle = json.loads((R / "S5_oracle_r1.json").read_text())
names = [c["name"] for c in oracle["details"]["reward"]["components"][0]["detail"]["criteria"]]
def checks(d):
    return {c["name"]: (c["raw"], int(c["weight"])) for c in d["details"]["reward"]["components"][0]["detail"]["criteria"]}
for f in sorted(R.glob("*.json")):
    d = json.loads(f.read_text())
    if "details" not in d:
        print(f.stem, "NO DETAILS", d.get("verify_rc")); continue
    c = checks(d)
    lost = [f"{n}({w})" for n, (raw, w) in c.items() if w > 0 and not raw]
    paid = [f"{n}({w})" for n, (raw, w) in c.items() if w > 0 and raw]
    neg = [n for n, (raw, w) in c.items() if w < 0 and raw]
    earned = sum(w for n, (raw, w) in c.items() if raw)
    print(f"{f.stem}: reward={d['reward']['reward']:.4f} earned={earned} solve_rc={d['solve_rc']} solve={d['solve_sec']}s verify={d['verify_sec']}s")
    if "-v" in sys.argv or f.stem in sys.argv[1:]:
        print("   LOST:", " ".join(lost)); print("   PAID:", " ".join(paid) if len(paid) < 20 else f"{len(paid)} checks"); print("   NEG:", neg)
