"""For candidate seeds: plant survivor envelopes, list survivor months, statuses, and which
artifacts' owned rows differ for H7 mutant and agent.  usage: explore_surv.py seed [seed...]"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402

PROGS = {"H7": "/fz/mut/H7/reconcile.py", "agent": "/fz/mut/agent/reconcile.py"}
NAMES = ["attention_allocation.csv", "month_load_index.csv", "commitment_ledger.jsonl",
         "actionable_queue.tsv", "blocked_commitments.csv", "deferred_queue.psv",
         "project_lineage.csv", "actor_rollup.json", "project_rollup.json",
         "audit_totals.csv", "reconciliation.txt", "escalation_queue.csv"]


def rows(path):
    name = os.path.basename(path)
    txt = open(path, encoding="utf-8").read()
    if name.endswith(".jsonl"):
        return [json.loads(x) for x in txt.split("\n") if x]
    sep = {"csv": ",", "tsv": "\t", "psv": "|"}[name.rsplit(".", 1)[1]]
    ls = [x for x in txt.split("\n") if x]
    h = ls[0].split(sep)
    return [dict(zip(h, x.split(sep))) for x in ls[1:]]


for seed in map(int, sys.argv[1:]):
    T.SURVIVOR_SEEDS = (seed,)
    tmp = tempfile.mkdtemp()
    data = T._write_corpus(seed, os.path.join(tmp, "data"))
    ref = os.path.join(tmp, "ref")
    os.makedirs(ref)
    T.write_all(T.compute(data), ref)
    groups = {}
    for r in rows(os.path.join(ref, "attention_allocation.csv")):
        groups.setdefault((r["year_month"], r["obligor_actor"]), []).append(r)
    months = set()
    for pair, rs in groups.items():
        held = [r for r in rs if int(r["allocated_minutes"]) > 0]
        lost = [r for r in rs if int(r["demand_minutes"]) > 0 and int(r["allocated_minutes"]) == 0]
        if held and lost and sum(int(r["allocated_minutes"]) for r in held) > sum(int(r["demand_minutes"]) for r in held):
            months.add(pair)
    keys = {r["commitment_key"] for p in months for r in groups[p]}
    held_keys = {r["commitment_key"] for p in months for r in groups[p] if int(r["allocated_minutes"]) > 0}
    cnt = {}
    for n in ["actionable_queue.tsv", "blocked_commitments.csv", "deferred_queue.psv"]:
        ks = {r["commitment_key"] for r in rows(os.path.join(ref, n))}
        cnt[n] = (len(ks & keys), len(ks & held_keys))
    res = {"seed": seed, "months": sorted(months), "keys": len(keys), "held": len(held_keys), "status": cnt}
    for lab, prog in PROGS.items():
        out = os.path.join(tmp, lab)
        os.makedirs(out)
        shutil.copy(prog, os.path.join(tmp, "reconcile.py"))
        p = subprocess.run([sys.executable, os.path.join(tmp, "reconcile.py"), data, out], capture_output=True)
        diff = []
        for n in NAMES:
            a = open(os.path.join(ref, n), "rb").read()
            b = open(os.path.join(out, n), "rb").read() if os.path.exists(os.path.join(out, n)) else b""
            if a != b:
                diff.append(n)
        res[lab] = {"exit": p.returncode, "diff": diff}
    print(json.dumps(res), flush=True)
    shutil.rmtree(tmp)
