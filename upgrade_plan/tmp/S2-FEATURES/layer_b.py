#!/usr/bin/env python3
"""Layer B (no AI): relate Layer A features to the Opus 5 tests score. Writes LAYER_B.txt."""
import csv, os, statistics as st, collections, re
D = os.path.dirname(os.path.abspath(__file__))
rows = [x for x in csv.DictReader(open(os.path.join(D, "FEATURES.csv"))) if x["opus_tests"] and x["t_checks"] != "0"]
y = [float(x["opus_tests"]) for x in rows]

def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i]); rk = [0.0] * len(v); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]: j += 1
        for k in range(i, j + 1): rk[order[k]] = (i + j) / 2
        i = j + 1
    return rk

def spearman(a, b):
    ra, rb = ranks(a), ranks(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((p - ma) * (q - mb) for p, q in zip(ra, rb))
    den = (sum((p - ma) ** 2 for p in ra) * sum((q - mb) ** 2 for q in rb)) ** 0.5
    return num / den if den else 0.0

skip = {"task", "opus_tests", "opus_rubric", "opus_final", "env_top_formats"}
out = [f"LAYER B, {len(rows)} teammate tasks with test details (Ayush's own 5 excluded). Target: Opus 5 tests percent (median {st.median(y)}).", ""]
out.append("NUMERIC FEATURES: Spearman correlation with Opus tests percent (negative = more of it goes with a LOWER Opus tests score)")
num = []
for c in rows[0]:
    if c in skip or c.startswith("ins_") and c != "ins_output_paths": continue
    try: v = [float(x[c]) for x in rows]
    except ValueError: continue
    if len(set(v)) < 3: continue
    num.append((spearman(v, y), c, st.median(v)))
for r, c, m in sorted(num): out.append(f"  {r:+.2f}  {c} (median {m:g})")
out += ["", "YES/NO FEATURES: how many tasks have it, and median Opus tests percent with and without it"]
for c in rows[0]:
    if not (c.startswith("ins_") and c != "ins_output_paths") and c not in ("test_py_seeded_generation", "test_py_runs_program"): continue
    w = [float(x["opus_tests"]) for x in rows if x[c] == "1"]; wo = [float(x["opus_tests"]) for x in rows if x[c] != "1"]
    out.append(f"  {c}: {len(w)} of {len(rows)} tasks; median with {st.median(w) if w else '-'}, without {st.median(wo) if wo else '-'}")
lost = list(csv.DictReader(open(os.path.join(D, "LOST_CHECKS.csv"))))
words = collections.Counter(); lostw = collections.Counter()
for x in lost:
    for t in set(re.findall(r"[a-z]{4,}", x["check"].lower())):
        words[t] += 1; lostw[t] += float(x["lost_weight"])
out += ["", f"TEST CHECK NAMES: {len(lost)} positive checks. Words most often in check names, with the total weight Opus lost on checks containing that word"]
for t, n in words.most_common(40): out.append(f"  {t}: in {n} checks, lost weight {lostw[t]:.1f}")
tot = sum(float(x["weight"]) for x in lost); tl = sum(float(x["lost_weight"]) for x in lost)
out += ["", f"Overall: Opus lost {tl:.1f} of {tot:.1f} positive test weight ({100 * tl / tot:.1f} percent)."]
open(os.path.join(D, "LAYER_B.txt"), "w").write("\n".join(out) + "\n")
print("\n".join(out))
