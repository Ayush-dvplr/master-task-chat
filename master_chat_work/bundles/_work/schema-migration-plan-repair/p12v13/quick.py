"""Inside Docker: one planner over listed graphs, each capped; prints a row per graph."""
import json
import subprocess
import sys

repo, cap, *graphs = sys.argv[1:]
for graph in graphs:
    try:
        done = subprocess.run([sys.executable, "-B", "/w/p12v13/run_plan.py", repo, "plan", graph],
                              capture_output=True, text=True, timeout=float(cap))
        lines = done.stdout.strip().splitlines()
        row = json.loads(lines[-1]) if lines else {"error": done.stderr[-600:]}
    except subprocess.TimeoutExpired:
        row = {"answer": "CAP", "seconds": float(cap)}
    answer = row.get("answer")
    print(graph, row.get("seconds"), answer if isinstance(answer, str) or answer is None else (len(answer), answer[:3]), row.get("error", ""), flush=True)
print("ALL_DONE", flush=True)
