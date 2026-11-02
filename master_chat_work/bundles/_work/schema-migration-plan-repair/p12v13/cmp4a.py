import json, subprocess, sys
rows = [json.loads(l) for l in open("stress_try1.jsonl")]
same = diff = 0
worst = 0.0
for r in rows:
    ref = r["ucs"] if r["ucs"].get("answer") not in (None, "CAP") else r["v12"]
    out = subprocess.run([sys.executable, "-B", "run_plan.py", "/w/p12v13/repo_try4a", "plan", "graphs/" + r["graph"]], capture_output=True, text=True, timeout=120)
    got = json.loads(out.stdout)
    worst = max(worst, got["seconds"])
    ok = got["answer"] == ref["answer"]
    same += ok; diff += not ok
    print(r["graph"], "same" if ok else "DIFF", got["seconds"], flush=True)
print("same", same, "diff", diff, "max_seconds", worst)
print("ALL_DONE")
