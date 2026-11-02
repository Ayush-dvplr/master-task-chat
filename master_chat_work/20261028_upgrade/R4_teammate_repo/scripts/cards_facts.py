#!/usr/bin/env python3
"""R4 card facts for the genuine models (read only). Re-run: python3 OUT/scripts/cards_facts.py -> OUT/cards_facts.md
TRUTH focal items + trajectory timeline of the main deliverable (create / runs / edits)."""
import glob, json, os, re
from datetime import datetime
REPO = "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = {"59417607": "transform.py", "aa314fee": "derive_report.py", "42e79476": "solver.py", "df8f123b": "report.json",
       "18b5d99f": "optimize.py", "6d12f970": "derive_report.py", "80202e15": "transform.py", "9f5486ac": "transform.py", "b5c7b14c": "reconcile.py"}
ts = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
md = []
for tid, prog in GEN.items():
    td = glob.glob(os.path.join(REPO, tid + "*"))[0]
    truth = open(os.path.join(td, "solution", "TRUTH.md"), errors="ignore").read().splitlines()
    items = [f"TRUTH:{i} {l.strip()[:230]}" for i, l in enumerate(truth, 1) if re.match(r"\s*\d+\.\s", l) and re.search(r"focal|trap|drift|Defeat", l, re.I)][:10]
    defeats = [f"TRUTH:{i} {l.strip()[:200]}" for i, l in enumerate(truth, 1) if "Defeat" in l][:8]
    t = json.load(open(glob.glob(os.path.join(td, "trajectories", "*", "run_1", "agent", "trajectory.json"))[0]))
    st = t["steps"]; t0 = ts(st[0]["timestamp"])
    ev = []
    for s in st:
        for c in s.get("tool_calls") or []:
            a = json.dumps(c.get("arguments", {}))
            if prog in a:
                kind = "create" if '"create"' in a or re.search(r"cat\s*>\s*\S*" + re.escape(prog), a) else ("run" if re.search(r"python3?\s+\S*" + re.escape(prog), a) else "edit/other")
                ev.append((s["step_id"], round((ts(s["timestamp"]) - t0).total_seconds() / 60, 1), kind))
    first = next((e for e in ev if e[2] == "create"), None)
    runs = [e for e in ev if e[2] == "run"]
    md.append(f"## {tid} ({prog}) steps={len(st)}")
    md.append(f"- first create: {first}; runs: {len(runs)} (first {runs[0] if runs else None}, last {runs[-1] if runs else None}); edit/other: {sum(1 for e in ev if e[2]=='edit/other')}")
    md += ["- " + x for x in items]
    md += ["- " + x for x in defeats if x not in items]
    md.append("")
open(os.path.join(OUT, "cards_facts.md"), "w").write("\n".join(md))
print("ok", len(md))
