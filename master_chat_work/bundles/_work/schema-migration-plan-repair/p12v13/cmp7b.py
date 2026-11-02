"""Inside Docker: try7 against exact references. Stress graphs use stress_try1.jsonl (plain UCS where it
finished, else the v12 planner); every other graph is compared with plain UCS run here (cap 90 s)."""
import json, subprocess, sys
NEW = "/w/p12v13/repo_try7"
def run(repo, graph, cap):
    try:
        out = subprocess.run([sys.executable, "-B", "run_plan.py", repo, "plan", graph], capture_output=True, text=True, timeout=cap)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {"answer": "CAP", "seconds": cap}
def run_ucs(graph, cap):
    try:
        out = subprocess.run([sys.executable, "-B", "run_plan.py", "/w/repo_fixed", "ucs", graph], capture_output=True, text=True, timeout=cap)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {"answer": "CAP", "seconds": cap}
refs = {}
for line in open("stress_try1.jsonl"):
    r = json.loads(line)
    refs["graphs/" + r["graph"]] = (r["ucs"] if r["ucs"].get("answer") not in (None, "CAP") else r["v12"])["answer"]
same = diff = noref = 0
for graph in sys.argv[1:]:
    got = run(NEW, graph, 60)
    ref = refs.get(graph)
    source = "stress_ref"
    if ref is None:
        r = run_ucs(graph, 90)
        ref, source = r["answer"], f"ucs {r['seconds']}s"
    if ref == "CAP":
        noref += 1; verdict = "NOREF"
    elif got["answer"] == ref:
        same += 1; verdict = "same"
    else:
        diff += 1; verdict = "DIFF"
    print(graph, verdict, got["seconds"], source, flush=True)
print("same", same, "diff", diff, "noref", noref)
print("ALL_DONE")
