import json, statistics, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import ROOT, pearson, load_all

rows = [json.loads(l) for l in open(ROOT / "master_chat_tasks/registry/scores.jsonl") if l.strip()]
runs = [(r["ist"], r["slug"], r["event"], r["rewards"]["tests"], r["rewards"]["rubric"], r["rewards"]["combined"])
        for r in rows if r.get("valid") is True and r.get("event") in ("probe", "gate_run") and r.get("rewards")]
print(f"O1 valid probe/gate_run rows in scores.jsonl: {len(runs)}")
for x in runs:
    print("  ", x)
t = [x[3] for x in runs]; j = [x[4] for x in runs]; f = [x[5] for x in runs]
print(f"O2 mean tests {statistics.mean(t):.1f} mean rubric {statistics.mean(j):.1f} mean final {statistics.mean(f):.1f}; "
      f"final<40 {sum(v < 40 for v in f)}, <50 {sum(v < 50 for v in f)}; tests==100 {sum(v == 100 for v in t)}; r(tests, rubric) {pearson(t, j):+.2f}")
g = [x for x in runs if x[2] == "gate_run"]
print(f"O3 gate runs {len(g)}: final<40 {sum(x[5] < 40 for x in g)}, <50 {sum(x[5] < 50 for x in g)}, tests<85 {sum(x[3] < 85 for x in g)}, "
      f"rubric<85 {sum(x[4] < 85 for x in g)}, mean tests {statistics.mean(x[3] for x in g):.1f} mean rubric {statistics.mean(x[4] for x in g):.1f}")
# rubric needed for final<40 at each of our gate-run test levels
for x in g:
    print(f"O4 {x[1]} {x[0][:10]}: tests {x[3]} rubric {x[4]} final {x[5]} -> rubric needed for <40: {80 - x[3]:.1f}; for <50: {100 - x[3]:.1f}")

# our pushed tasks that also sit in Final_Delivery (matched by stored tests/judge %; author Ayush Sah)
T = {d["id"][:8]: d for d in load_all(with_inputs=False)}
for slug, tid in (("dispatch-plan-reoptimization", "42e79476"), ("emberforge-vault-settlement", "b47fd5f7"),
                  ("match-replay-desync-audit", "8fbe0e42"), ("caldermoor-commitment-closure", "b5c7b14c")):
    d = T[tid]
    print(f"O5 {slug} = FD {tid}: FD report tests {d['tests_pct']} judge {d['judge_pct']} final {d['final']} author {d.get('author')}")
