"""try7 vs try2 (plain backward symbolic Dijkstra, uncompiled, no bound) on the adversarial graphs."""
import json, subprocess, sys
def run(repo, graph, cap):
    try:
        d = subprocess.run([sys.executable, "-B", "/w/p12v13/run_plan.py", repo, "plan", graph], capture_output=True, text=True, timeout=cap)
        return json.loads(d.stdout.strip().splitlines()[-1])
    except Exception as e:
        return {"answer": "CAP/ERR " + type(e).__name__, "seconds": cap}
same = diff = 0
for g in sys.argv[1:]:
    a = run("/w/p12v13/repo_try7", g, 60); b = run("/w/p12v13/repo_try2", g, 120)
    ok = a["answer"] == b["answer"] and not str(b["answer"]).startswith("CAP")
    same += ok; diff += not ok
    print(g, "same" if ok else "DIFF", a["seconds"], "try2", b["seconds"], flush=True)
print("same", same, "diff", diff); print("ALL_DONE", flush=True)
