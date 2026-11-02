"""Merge sentinel (manual) + auto rows into FINDINGS.csv and print aggregate stats for ANALYSIS/PROPOSALS."""
import csv, collections as C, re
from pathlib import Path
W = Path(__file__).parent; OUT = W.parent
cols = ["task","qc_version","qc_sha","finding_id","rule_id","severity","file_line","summary","origin","cause_evidence","resolution_next_round","caused_new_finding"]
sent = list(csv.DictReader(open(W / "sentinel-policy-recompute.csv")))
auto = list(csv.DictReader(open(W / "auto_findings_attrib.csv")))
for r in sent:
    r["prompt_attrib"] = ""; r["pattern"] = ""
    ev = r["cause_evidence"]
    if r["origin"] in ("FIX_CAUSED",) or "LATENT_FIX" in ev:
        r["prompt_attrib"] = "prompt-asked" if ("prompt-asked" in ev) else "session own choice"
for r in auto:
    if r["prompt_attrib"]:
        r["cause_evidence"] = (r["cause_evidence"] + " | " + r["prompt_attrib"] + (" | pattern: " + r["pattern"] if r["pattern"] else ""))[:400]
rows = sent + auto
with open(OUT / "FINDINGS.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def P(*a): print(*a)
P("TOTAL", len(rows))
post = [r for r in rows if r["origin"] != "BASELINE"]
P("post-v1", len(post))
oc = C.Counter(r["origin"] for r in rows); P("by_origin all", dict(oc))
ocp = C.Counter(r["origin"] for r in post); P("by_origin post", dict(ocp), {k: round(v / len(post), 3) for k, v in ocp.items()})
latent = [r for r in rows if "LATENT_FIX" in r["cause_evidence"]]; P("sentinel latent", len(latent))
P("unverified (no copy)", sum(1 for r in post if "UNVERIFIED" in r["cause_evidence"]))
# per task per round
tbl = C.defaultdict(C.Counter)
for r in rows:
    tbl[(r["task"], r["qc_version"])][r["origin"]] += 1
    tbl[(r["task"], r["qc_version"])]["sev_" + r["severity"]] += 1
ORDER = ["BASELINE","FIX_CAUSED","HARDEN_CAUSED","MISSED_EARLIER","REFLAG_KEPT","REFLAG_FIXED","RULE_CONFLICT","NEW_RULE"]
P("|task|ver|F/M/W|" + "|".join(o[:9] for o in ORDER) + "|")
for (t, v), c in sorted(tbl.items(), key=lambda x: (x[0][0], int(x[0][1][1:]))):
    P(f"|{t.split('-')[0]}|{v}|{c['sev_fail']}/{c['sev_minor']}/{c['sev_warn']}|" + "|".join(str(c[o]) for o in ORDER) + "|")
# per task totals
pt = C.defaultdict(C.Counter)
for r in rows: pt[r["task"]][r["origin"]] += 1
for t, c in pt.items(): P("TASK", t.split('-')[0], sum(c.values()), dict(c))
# severity by origin
P("sev x origin", {o: dict(C.Counter(r["severity"] for r in post if r["origin"] == o)) for o in ORDER})
# attribution
fc = [r for r in rows if r["origin"] in ("FIX_CAUSED",)]
P("FIX_CAUSED", len(fc), "asked", sum(1 for r in fc if "prompt-asked" in (r["prompt_attrib"] or r["cause_evidence"])), "copies-QC-fix", sum(1 for r in fc if "copies QC" in r["cause_evidence"] or "copied from QC" in r["cause_evidence"] or "Fix text" in r["cause_evidence"] or "Fix lines" in r["cause_evidence"]))
P("patterns", C.Counter(p for r in auto if r["origin"] == "FIX_CAUSED" for p in (r["pattern"] or "none").split(";")))
P("FIX_CAUSED rules", C.Counter(r["rule_id"] for r in fc).most_common(12))
# top rules
P("top rules all", C.Counter(r["rule_id"] for r in rows).most_common(15))
P("top rules post", C.Counter(r["rule_id"] for r in post).most_common(12))
# task-rounds per rule
tr = C.Counter(); seen = set()
for r in rows:
    k = (r["rule_id"], r["task"], r["qc_version"])
    if k not in seen: seen.add(k); tr[r["rule_id"]] += 1
P("task-rounds per rule", tr.most_common(12))
# rounds per task where rule recurs >=3
rec = C.Counter()
for (rule, t), n in C.Counter((r["rule_id"], r["task"]) for r in rows).items():
    if n >= 3: rec[(rule, t.split('-')[0])] = n
P("recurring >=3 in one task", rec.most_common(15))
# split-vs-cap
split_ids = {"TS-13", "TS-20", "CL-4", "TS-26"}
P("split-side findings", sum(1 for r in rows if r["rule_id"] in split_ids), "post", sum(1 for r in post if r["rule_id"] in split_ids))
P("cap findings TS-23/A3", sum(1 for r in rows if r["rule_id"] in ("TS-23", "A3")), [(r["task"][:8], r["qc_version"], r["origin"]) for r in rows if r["rule_id"] in ("TS-23", "A3")])
# variance in rounds >=3
P("MISSED_EARLIER in v>=3", sum(1 for r in post if r["origin"] == "MISSED_EARLIER" and int(r["qc_version"][1:]) >= 3), "REFLAG in v>=3", sum(1 for r in post if r["origin"].startswith("REFLAG") and int(r["qc_version"][1:]) >= 3))
P("post v>=3 total", sum(1 for r in post if int(r["qc_version"][1:]) >= 3))
P("fails post by origin", dict(C.Counter(r["origin"] for r in post if r["severity"] == "fail")))
P("judge-file findings post", C.Counter(r["origin"] for r in post if "judge.toml" in r["file_line"]))
P("doc consistency (DS-22/AL-18/TS-14/DS-27)", sum(1 for r in post if r["rule_id"] in ("DS-22", "AL-18", "TS-14", "DS-27", "DS-21", "AL-19", "TS-24")))
