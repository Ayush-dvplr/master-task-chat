"""Planner timing on cyclic graphs with astronomically many paths."""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import migrakit

FIELDS = ["f%d" % i for i in range(10)]


def build(folder: Path, schemas: int, parallel: int, seed: int, opheavy: bool):
    rng = random.Random(seed)
    folder.mkdir(parents=True, exist_ok=True)
    entries = [{"id": f"d.v{i}", "domain": "d", "canonical": i == schemas} for i in range(1, schemas + 1)]
    rows = ["edge_id,source,target,requires,operations,cost"]
    n = 0
    for i in range(1, schemas):
        for k in range(parallel):
            ops = []
            if opheavy:
                if rng.random() < 0.7:
                    a, b = rng.sample(FIELDS, 2)
                    ops.append(f"rename:{a}>{b}")
                if rng.random() < 0.5:
                    ops.append(f"add:{rng.choice(FIELDS)}")
                if rng.random() < 0.5:
                    ops.append(f"drop:{rng.choice(FIELDS)}")
            else:
                ops.append(f"cast:{rng.choice(FIELDS)}:str")
            req = [f"{rng.choice(['has', 'lacks'])}:{f}" for f in rng.sample(FIELDS, rng.randint(0, 2))]
            rows.append(f"E{n:05d},d.v{i},d.v{i + 1},{';'.join(req)},{';'.join(ops)},{rng.randint(1, 9)}")
            n += 1
        if i > 1:
            rows.append(f"E{n:05d},d.v{i},d.v{i - 1},,,{rng.randint(1, 9)}")
            n += 1
    policy = ["domain\tfield\tdefault\tfill\tnull_counts_as"]
    for f in FIELDS:
        policy.append(f"d\t{f}\t{rng.choice(['', '1'])}\t\t{rng.choice(['', 'present', 'absent'])}")
    (folder / "schema_versions.json").write_text(json.dumps({"schemas": entries}))
    (folder / "migration_edges.csv").write_text("\n".join(rows) + "\n")
    (folder / "field_policy.tsv").write_text("\n".join(policy) + "\n")
    (folder / "null_semantics.ini").write_text("[presence]\nexplicit_null = present\n[fill]\nmode = absent_only\n[tokens]\ndefault = NULL\n")
    (folder / "partner_aliases.xml").write_text('<partners><partner id="P1"/></partners>')
    (folder / "report_taxonomy.json").write_text(json.dumps({"categories": []}))
    (folder / "partner_order.tsv").write_text("partner_id\trank\n")
    return n


def run(label, schemas, parallel, opheavy, trials=5):
    folder = Path(sys.argv[3]) / ("stress_%s" % label)
    edges = build(folder, schemas, parallel, 3, opheavy)
    registry = migrakit.load_contracts(folder)
    rng = random.Random(5)
    worst = 0.0
    lengths = []
    for _ in range(trials):
        payload = {f: rng.choice([None, 1, "x"]) for f in FIELDS if rng.random() < 0.7}
        t0 = time.perf_counter()
        try:
            lengths.append(len(migrakit.plan_migration(registry, "d.v1", payload)))
        except migrakit.MigrationError as exc:
            lengths.append(exc.code)
        worst = max(worst, time.perf_counter() - t0)
    print(f"{label}: schemas={schemas} edges={edges} opheavy={opheavy} worst={worst:.2f}s plans={lengths}", flush=True)


import sys as _s
CFG={"thin":(81,3,False),"thin_ops":(81,3,True),"wide":(81,20,True),"wide_plain":(81,70,False),"huge":(81,70,True)}
run(_s.argv[2],*CFG[_s.argv[2]])
