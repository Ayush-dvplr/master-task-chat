#!/usr/bin/env python3
"""R4 per-task loss dump (read only). Re-run: python3 OUT/scripts/losses.py
Writes OUT/losses.json (all 90) and OUT/losses_models.md (13 models + band-edge cases).
Convention checked on 725e575c: negative test passed=False means penalty NOT applied
(tests_pct 96.55 = (145-5)/145 with all negatives passed=False).
Rubric negatives: penalty APPLIED when passed=False (checked: reconciles rubric_weights_percentage on 90/90)."""
import json, os, glob, re

REPO = "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ["8defd7be", "42e79476", "59417607", "aa314fee", "9f5486ac", "d49e259f", "5b2b0901",
          "df8f123b", "b5c7b14c", "6d12f970", "80202e15", "725e575c", "18b5d99f"]
EXTRA = ["d22ff871"]


def readme_scores():
    s = {}
    for line in open(os.path.join(REPO, "README.md")):
        m = re.match(r"\| \[`([0-9a-f]{8})`\].*?\| ([0-9.]+) \|", line)
        if m: s.setdefault(m.group(1), float(m.group(2)))
    return s


def main():
    rs = readme_scores()
    allrows = {}
    md = []
    for td in sorted(glob.glob(os.path.join(REPO, "*-*-*-*-*"))):
        tid = os.path.basename(td)[:8]
        runs = sorted(glob.glob(os.path.join(td, "trajectories", "*", "run_*")))
        per = []
        for run in runs:
            rep = json.load(open(os.path.join(run, "report.json")))
            tests = rep["pytest"]["tests"]
            pos = [t for t in tests if t["weight"] > 0]
            wsum = sum(t["weight"] for t in pos)
            per.append(dict(
                run=os.path.relpath(run, td), final=rep["final_reward"],
                tests_pct=rep["test_weights_percentage"], rubric_pct=rep["rubric_weights_percentage"],
                judge=rep.get("judge_model"),
                failed=[(t["name"], t["weight"], round(100 * t["weight"] / wsum, 1)) for t in pos if not t["passed"]],
                neg_fired=[(t["name"], t["weight"]) for t in tests if t["weight"] < 0 and t["passed"]],
                rub_failed=[(c["number"], c["score"], c.get("evaluation_target"), c["criterion"][:160], c.get("justification", "")[:300])
                            for c in rep.get("rubric", []) if c.get("is_positive", True) and not c.get("passed")],
                rub_neg_fired=[(c["number"], c["score"], c["criterion"][:160], c.get("justification", "")[:300])
                               for c in rep.get("rubric", []) if not c.get("is_positive", True) and not c.get("passed")],
            ))
        allrows[tid] = dict(readme=rs.get(tid), n_runs=len(runs), runs=per)
        if tid in MODELS + EXTRA:
            p = per[0]
            md.append(f"## {tid} readme={rs.get(tid)} runs={len(runs)} final={p['final']} tests={p['tests_pct']} rubric={p['rubric_pct']} judge={p['judge']}")
            md.append("failed tests (name, w, %of pos):")
            md += [f"- {f}" for f in p["failed"]]
            md.append(f"neg tests fired: {p['neg_fired']}")
            md.append("rubric failed (positive):")
            md += [f"- #{n} w{w} [{t}] {c} || {j}" for n, w, t, c, j in p["rub_failed"]]
            md.append("rubric negatives fired:")
            md += [f"- #{n} w{w} {c} || {j}" for n, w, c, j in p["rub_neg_fired"]]
            md.append("")
    json.dump(allrows, open(os.path.join(OUT, "losses.json"), "w"), indent=1)
    open(os.path.join(OUT, "losses_models.md"), "w").write("\n".join(md))
    mism = [(k, v["readme"], v["runs"][0]["final"], v["n_runs"]) for k, v in allrows.items()
            if v["readme"] is not None and abs(v["readme"] * 100 - v["runs"][0]["final"]) > 1]
    print("tasks", len(allrows), "multi-run", sum(1 for v in allrows.values() if v["n_runs"] > 1))
    print("readme vs run_1 mismatch >1pt:", mism)


if __name__ == "__main__":
    main()
