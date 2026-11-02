#!/usr/bin/env python3
"""Run solve_proto with each reflex reading on each corpus and report which documents differ."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1]
CORPORA = sys.argv[2].split(",")
VARIANTS = ["fit", "pinv", "pstrict", "prel", "exall", "exincl", "exonce", "fit,pinv,exall", "fit,pstrict,exincl"]
DOCS = ["summary.json", "policy_audit.json", "data_quality.json"] + \
    [f"region_{s}.json" for s in ["North", "South", "West", "East"]] + \
    [f"segment_{g}.json" for g in ["commercial", "public"]]


def run(corpus, rx, out):
    subprocess.run([sys.executable, "-B", os.path.join(HERE, "solve_proto.py"), "--data", os.path.join(ROOT, corpus),
                    "--out", out, "--reflex", rx], check=True)


def load(d, n):
    with open(os.path.join(d, n)) as fh:
        return json.load(fh)


print("| reading | " + " | ".join(CORPORA) + " |")
print("|---|" + "---|" * len(CORPORA))
for rx in VARIANTS:
    cells = []
    for c in CORPORA:
        ref = os.path.join(ROOT, "out", c)
        out = os.path.join(ROOT, "out", f"{c}__{rx.replace(',', '+')}")
        run(c, rx, out)
        bad = [n.replace(".json", "") for n in DOCS if load(ref, n) != load(out, n)]
        ra = {r["invoice_id"]: r for r in load(ref, "policy_audit.json")["rows"]}
        rb = {r["invoice_id"]: r for r in load(out, "policy_audit.json")["rows"]}
        rows = sum(1 for k in ra if ra[k] != rb.get(k))
        cells.append(f"{len(bad)}/9 docs, {rows} rows" if bad else "exact")
    print(f"| {rx} | " + " | ".join(cells) + " |")
