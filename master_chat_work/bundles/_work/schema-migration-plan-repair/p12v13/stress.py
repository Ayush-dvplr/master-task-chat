"""Inside Docker: every graph through new planner, plain uniform-cost search and the v12 planner, each capped."""
import json
import subprocess
import sys
from pathlib import Path

W = Path("/w")
graphs = sys.argv[2:]
out = Path(sys.argv[1])
runs = [("new", "/w/repo_fixed", "plan", 60), ("ucs", "/w/repo_fixed", "ucs", 150), ("v12", "/w/p12v13/repo_v12", "plan", 150)]
with out.open("a") as log:
    for graph in graphs:
        row = {"graph": Path(graph).name}
        for tag, repo, mode, cap in runs:
            try:
                done = subprocess.run(
                    [sys.executable, "-B", "/w/p12v13/run_plan.py", repo, mode, graph],
                    capture_output=True, text=True, timeout=cap,
                )
                line = done.stdout.strip().splitlines()
                row[tag] = json.loads(line[-1]) if line else {"error": done.stderr[-400:]}
            except subprocess.TimeoutExpired:
                row[tag] = {"answer": "CAP", "seconds": cap}
        log.write(json.dumps(row) + "\n")
        log.flush()
    log.write("ALL_DONE\n")
