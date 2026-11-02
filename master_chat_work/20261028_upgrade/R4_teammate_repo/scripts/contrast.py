#!/usr/bin/env python3
"""R4 contrast across all 90 (read only). Re-run: python3 OUT/scripts/contrast.py
Inputs: OUT/inventory.json (scripts/inventory.py) + repo files. Writes OUT/contrast.md and OUT/features.csv.
Columns prefixed h_ are keyword heuristics (INFERRED)."""
import csv, glob, json, os, re, statistics as st
from collections import Counter, defaultdict

REPO = "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN = re.compile(r"hidden|unseen|fresh|eval_|slice_|decoy_|generalis|_instance|wk\d|_hard|held|full_ledger|full_mode|mode_bit|every_bit|"
                    r"program_reproduces|scale|large|timed|stage2|trap_|_extract_exact|later_stage|variant|perturb|mutat|random|seeded", re.I)
INDUCE = re.compile(r"withheld|not stated|no file states|undocumented|recover (the|every|its)|digest|figures are (both )?missing|"
                    r"none of its numbers|absent rule|must be inferred|infer", re.I)
FIG = re.compile(r"\b\d{3,}\b")


def grp(b): return "HardExpert" if b in ("Hard", "Expert") else b


def main():
    inv = {r["id"]: r for r in json.load(open(os.path.join(OUT, "inventory.json")))}
    rows = []
    for tid, r in inv.items():
        td = glob.glob(os.path.join(REPO, tid + "*"))[0]
        rep = json.load(open(glob.glob(os.path.join(td, "trajectories", "*", "run_1", "report.json"))[0]))
        tests = rep["pytest"]["tests"]; pos = [t for t in tests if t["weight"] > 0]
        W = sum(t["weight"] for t in pos)
        hid = [t for t in pos if HIDDEN.search(t["name"])]
        shp = [t for t in pos if not HIDDEN.search(t["name"])]
        rub = rep["rubric"]; rp = [c for c in rub if c["is_positive"]]; rn = [c for c in rub if not c["is_positive"]]
        P = sum(c["score"] for c in rp)
        figs = [c for c in rp if FIG.search(c["criterion"]) and c.get("evaluation_target") in ("final_answer", "user_facing_message", "trajectory")
                and re.search(r"states|reports|gives", c["criterion"])]
        traj = [c for c in rp if c.get("evaluation_target") == "trajectory" and c not in figs]
        instr = open(os.path.join(td, "instruction.md"), errors="ignore").read()
        truth_p = os.path.join(td, "solution", "TRUTH.md")
        truth = open(truth_p, errors="ignore").read() if os.path.exists(truth_p) else ""
        rows.append(dict(
            id=tid, band=r["band"], grp=grp(r["band"]), final=r["final"], tests=r["tests_pct"], rubric=r["rubric_pct"],
            author=r["toml_author"], category=r["category"],
            loss_tests=round((100 - r["tests_pct"]) / 2, 1), loss_judge=round((100 - r["rubric_pct"]) / 2, 1),
            n_tests=len(pos), h_hidden_wshare=round(sum(t["weight"] for t in hid) / W, 3) if W else 0,
            h_hidden_mean_w=round(st.mean([t["weight"] for t in hid]), 2) if hid else 0,
            h_shipped_mean_w=round(st.mean([t["weight"] for t in shp]), 2) if shp else 0,
            h_hidden_pass=round(sum(t["weight"] for t in hid if t["passed"]) / sum(t["weight"] for t in hid), 3) if hid else None,
            h_shipped_pass=round(sum(t["weight"] for t in shp if t["passed"]) / sum(t["weight"] for t in shp), 3) if shp else None,
            top1=r["top1_share"], distinct_w=r["distinct_weights"],
            tp_subprocess=r["h_tp_subprocess"], tp_seeded=r["h_tp_random"],
            n_rub=len(rub), n_rub_neg=len(rn), rub_P=P, rub_fig_share=round(sum(c["score"] for c in figs) / P, 3) if P else 0,
            rub_trajprobe_share=round(sum(c["score"] for c in traj) / P, 3) if P else 0,
            rub_neg_applied_w=sum(abs(c["score"]) for c in rn if not c["passed"]),
            final_pts_per_neg_w=round(50 / P, 2) if P else None,
            h_induction_instr=bool(INDUCE.search(instr)), h_induction_truth=bool(re.search(r"withheld|undocumented|named nowhere|never given|no file states|none of its numbers|missing constants", truth, re.I)),
            instr_words=r["instr_words"], n_data_files=r["n_data_files"], data_kb=r["data_kb"],
            agent_min=r["agent_min"], steps=r["steps"], first_write_min=r["first_write_min"], selftests=r["h_selftest_cmds"],
            timeout_min=round(float(r["agent_timeout"]) / 60) if r["agent_timeout"] else None,
            used_time_share=round(r["agent_min"] / (float(r["agent_timeout"]) / 60), 2) if r["agent_min"] and r["agent_timeout"] else None,
            truth_bytes=len(truth),
        ))
    with open(os.path.join(OUT, "features.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    md = ["# Contrast across 90 (scripts/contrast.py output)\n"]
    groups = ["HardExpert", "Medium", "Easy"]
    num = ["final", "tests", "rubric", "loss_tests", "loss_judge", "n_tests", "h_hidden_wshare", "h_hidden_mean_w", "h_shipped_mean_w",
           "h_hidden_pass", "h_shipped_pass", "top1", "distinct_w", "n_rub", "n_rub_neg", "rub_P", "rub_fig_share", "rub_trajprobe_share",
           "rub_neg_applied_w", "instr_words", "n_data_files", "data_kb", "agent_min", "steps", "first_write_min", "selftests", "used_time_share", "truth_bytes"]
    md.append("| feature | " + " | ".join(f"{g} (n={sum(1 for r in rows if r['grp']==g)}) median" for g in groups) + " |")
    md.append("|---|" + "---|" * len(groups))
    for k in num:
        cells = []
        for g in groups:
            v = [r[k] for r in rows if r["grp"] == g and r[k] is not None]
            cells.append(f"{st.median(v):.3g}" if v else "-")
        md.append(f"| {k} | " + " | ".join(cells) + " |")
    md.append("")
    for k in ["tp_subprocess", "tp_seeded", "h_induction_instr", "h_induction_truth"]:
        md.append(f"- {k}: " + "; ".join(f"{g} {sum(1 for r in rows if r['grp']==g and r[k])}/{sum(1 for r in rows if r['grp']==g)}" for g in groups))
    md.append("\n## Which side loses the points (count of tasks where judge loss > tests loss)")
    for g in groups:
        sel = [r for r in rows if r["grp"] == g]
        md.append(f"- {g}: judge-dominant {sum(1 for r in sel if r['loss_judge'] > r['loss_tests'])}/{len(sel)}; tests<85 {sum(1 for r in sel if r['tests'] < 85)}; rubric<85 {sum(1 for r in sel if r['rubric'] < 85)}; final<40 {sum(1 for r in sel if r['final'] < 40)}")
    md.append("\n## Our gate (tests<85 AND rubric<85 AND final<40) across 90")
    gate = [r for r in rows if r["tests"] < 85 and r["rubric"] < 85 and r["final"] < 40]
    md.append(f"- pass: {len(gate)} -> {[r['id'] for r in gate]}")
    md.append("\n## Confound: contributor (toml author) -> bands")
    by = defaultdict(Counter)
    for r in rows: by[r["author"]][r["grp"]] += 1
    for a, c in sorted(by.items(), key=lambda x: -x[1]["HardExpert"]):
        fins = [r["final"] for r in rows if r["author"] == a]
        md.append(f"- {a}: n={sum(c.values())} HardExpert={c['HardExpert']} Medium={c['Medium']} Easy={c['Easy']} median_final={st.median(fins):.1f}")
    md.append("\n## Confound: category -> bands")
    byc = defaultdict(Counter)
    for r in rows: byc[r["category"]][r["grp"]] += 1
    for a, c in sorted(byc.items(), key=lambda x: -sum(x[1].values())):
        md.append(f"- {a}: n={sum(c.values())} HardExpert={c['HardExpert']} Medium={c['Medium']} Easy={c['Easy']}")
    md.append("\n## Within-contributor contrast (authors with both HardExpert and Easy tasks)")
    for a, c in by.items():
        if c["HardExpert"] and c["Easy"]:
            for g in ("HardExpert", "Easy"):
                sel = [r for r in rows if r["author"] == a and r["grp"] == g]
                md.append(f"- {a} {g}: " + "; ".join(f"{r['id']} f{r['final']} t{r['tests']} hidW{r['h_hidden_wshare']} hidPass{r['h_hidden_pass']} shpPass{r['h_shipped_pass']} induce{int(r['h_induction_truth'])} figs{r['rub_fig_share']}" for r in sel))
    md.append("\n## 13 models + judge sensitivity (final points per 1 judge weight = 50/P)")
    for r in sorted([r for r in rows if r["grp"] == "HardExpert"], key=lambda r: r["final"]):
        md.append(f"- {r['id']} f{r['final']} tests{r['tests']} rub{r['rubric']} lossT{r['loss_tests']} lossJ{r['loss_judge']} P{r['rub_P']} pts/w {r['final_pts_per_neg_w']} negApplied{r['rub_neg_applied_w']} hidW{r['h_hidden_wshare']} hidMeanW{r['h_hidden_mean_w']} shpMeanW{r['h_shipped_mean_w']} shpPass{r['h_shipped_pass']} induce{int(r['h_induction_truth'])} used{r['used_time_share']}")
    md.append("\n## Split tests (final medians, across 90)")
    def show(name, pred):
        a = [r for r in rows if pred(r)]; b = [r for r in rows if not pred(r)]
        he = lambda s: sum(1 for r in s if r["grp"] == "HardExpert")
        md.append(f"- {name}: yes n={len(a)} median_final={st.median(r['final'] for r in a):.1f} HE={he(a)} | "
                  f"no n={len(b)} median_final={st.median(r['final'] for r in b):.1f} HE={he(b)}")
    show("induction in TRUTH (withheld/undocumented)", lambda r: r["h_induction_truth"])
    show("hidden weight share >=0.5", lambda r: r["h_hidden_wshare"] >= 0.5)
    show("hidden mean weight exceeds shipped by >=1.5", lambda r: r["h_hidden_mean_w"] - r["h_shipped_mean_w"] >= 1.5)
    show("judge exact-figure share >=0.25", lambda r: r["rub_fig_share"] >= 0.25)
    show("judge P<=20", lambda r: r["rub_P"] <= 20)
    show("induction AND hidden share>=0.5", lambda r: r["h_induction_truth"] and r["h_hidden_wshare"] >= 0.5)
    open(os.path.join(OUT, "contrast.md"), "w").write("\n".join(md))
    print("wrote contrast.md, features.csv", len(rows))


if __name__ == "__main__":
    main()
