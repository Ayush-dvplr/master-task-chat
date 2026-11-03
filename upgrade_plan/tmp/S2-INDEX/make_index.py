#!/usr/bin/env python3
"""Phase 0 index of anubis-stage-2 (no AI). Reads origin/main via git, writes INDEX.csv and SUMMARY.txt."""
import subprocess, json, re, csv, sys, os, collections
REF = "origin/main"; ROOT = "anubis-stage-2"
OUT = os.path.dirname(os.path.abspath(__file__))
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
def show(p):
    r = subprocess.run(["git", "show", f"{REF}:{p}"], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None
sizes = collections.defaultdict(lambda: collections.Counter())
for line in git("ls-tree", "-r", "-l", REF, ROOT).splitlines():
    meta, path = line.split("\t", 1)
    sz = meta.split()[3]; sz = int(sz) if sz.isdigit() else 0
    parts = path.split("/")
    if len(parts) < 3: continue
    t = parts[1]; sizes[t]["files"] += 1
    if parts[2] == "environment" and len(parts) > 3 and parts[3] in ("data", "docs"): sizes[t][parts[3] + "_bytes"] += sz
rows = []
for t in sorted(sizes):
    base = f"{ROOT}/{t}"
    toml = show(f"{base}/task.toml") or ""
    def tv(k):
        m = re.search(r'^%s\s*=\s*"?([^"\n]*)"?' % re.escape(k), toml, re.M); return m.group(1) if m else ""
    ins = show(f"{base}/instruction.md") or ""
    tests = show(f"{base}/tests/test_output.py") or ""
    judge = show(f"{base}/tests/judge.toml") or ""
    crit_w = [float(x) for x in re.findall(r'^\s*weight\s*=\s*(-?[\d.]+)', judge.split("[[criterion]]", 1)[-1], re.M)] if "[[criterion]]" in judge else []
    row = {"task": t, "category": tv("category"), "verifier_timeout_s": tv("timeout_sec"),
           "instruction_words": len(ins.split()), "data_kb": sizes[t]["data_bytes"] // 1024, "docs_kb": sizes[t]["docs_bytes"] // 1024,
           "test_checks_est": (lambda m: round(1/float(m.group(1))) if m and float(m.group(1))>0 else "")(re.search(r'test_output\s*=\s*([\d.eE-]+)', show(f"{base}/tests/reward.toml") or "")),
           "rubric_criteria": judge.count("[[criterion]]"), "rubric_negative": sum(1 for w in crit_w if w < 0),
           "description": tv("description")[:160]}
    for model, key in (("claude-opus-5", "opus"), ("glm-5.3", "glm")):
        ps = show(f"{base}/trajectories/{model}/pass_summary.json")
        try:
            d = json.loads(ps) if ps else {}
        except Exception:
            d = {}
        row[f"{key}_runs"] = d.get("runs", "")
        row[f"{key}_tests"] = d.get("average_test_weights_percentage", "")
        row[f"{key}_rubric"] = d.get("average_rubric_weights_percentage", "")
        row[f"{key}_final"] = d.get("average_combined_score", "")
    o = row["opus_tests"], row["opus_rubric"], row["opus_final"]
    row["under_gate"] = "yes" if all(isinstance(x, (int, float)) for x in o) and o[0] < 85 and o[1] < 85 and o[2] < 40 else ("no" if all(isinstance(x, (int, float)) for x in o) else "no_score")
    rows.append(row)
cols = ["task", "category", "opus_runs", "opus_tests", "opus_rubric", "opus_final", "under_gate", "glm_runs", "glm_tests", "glm_rubric", "glm_final",
        "test_checks_est", "rubric_criteria", "rubric_negative", "instruction_words", "data_kb", "docs_kb", "verifier_timeout_s", "description"]
with open(os.path.join(OUT, "INDEX.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
sc = [r for r in rows if r["under_gate"] != "no_score"]
s = []
s.append(f"tasks: {len(rows)}; with Opus score: {len(sc)}; under gate (tests<85, rubric<85, final<40): {sum(r['under_gate']=='yes' for r in rows)}")
for k in ("opus_final", "opus_tests", "opus_rubric"):
    v = sorted(r[k] for r in sc); 
    if v: s.append(f"{k}: min {v[0]} median {v[len(v)//2]} max {v[-1]}")
b = collections.Counter(min(int(r["opus_final"]) // 10 * 10, 90) for r in sc)
s.append("opus_final buckets: " + ", ".join(f"{k}s: {b[k]}" for k in sorted(b)))
s.append("runs per task (Opus): " + str(dict(collections.Counter(r["opus_runs"] for r in rows))))
s.append("categories: " + str(dict(collections.Counter(r["category"] for r in rows).most_common())))
s.append("only one gate part missed: tests>=85: %d, rubric>=85: %d, final 40 to 50: %d" % (
    sum(1 for r in sc if r["opus_tests"] >= 85), sum(1 for r in sc if r["opus_rubric"] >= 85), sum(1 for r in sc if 40 <= r["opus_final"] < 50)))
open(os.path.join(OUT, "SUMMARY.txt"), "w").write("\n".join(s) + "\n")
print("\n".join(s))
