"""K14-limit probe: layered graph, 8 prerequisite fields, every edge adds one field and drops the next,
so the exit (has:f0..has:f7) can never apply after the first edge, yet each field alone can be present."""
import json, random, sys
from pathlib import Path
root = Path(sys.argv[1]); width = int(sys.argv[2]); layers_n = int(sys.argv[3]); outdeg = int(sys.argv[4]); bypass = sys.argv[5] == "1"
root.mkdir(parents=True, exist_ok=True)
rng = random.Random(11)
F = [f"f{i}" for i in range(8)]
layers = [["d.s"]] + [[f"d.l{k:02d}n{j:02d}" for j in range(width)] for k in range(layers_n)]
schemas = [{"id": s, "domain": "d", "canonical": False} for L in layers for s in L] + [{"id": "d.t", "domain": "d", "canonical": True}]
rows = ["edge_id,source,target,requires,operations,cost"]; n = 0
for here, there in zip(layers, layers[1:]):
    for a in here:
        for b in rng.sample(there, min(outdeg, len(there))):
            j = rng.randrange(8); n += 1
            A = F + ["g0", "g1"]
            x, y = rng.sample(A, 2)
            first = rng.choice([f"rename:{x}>{y}", f"add:{x}", f"drop:{x}", f"rename:{x}>{y}"])
            rows.append(f"E{n:05d},{a},{b},,{first};add:{F[j]};drop:{F[(j+1)%8]},1")
for a in layers[-1]:
    n += 1; rows.append(f"E{n:05d},{a},d.t,{';'.join('has:'+f for f in F)},,1")
if bypass:
    n += 1; rows.append(f"E{n:05d},d.s,d.t,,,100000")
files = {
 "schema_versions.json": json.dumps({"schemas": schemas}),
 "migration_edges.csv": "\n".join(rows) + "\n",
 "field_policy.tsv": "domain\tfield\tdefault\tfill\tnull_counts_as\n" + "".join(f"d\t{f}\t1\t\t\n" for f in F + ["g0", "g1"]),
 "null_semantics.ini": "[presence]\nexplicit_null = present\n\n[fill]\nmode = absent_only\n\n[tokens]\ndefault = NULL\n",
 "partner_aliases.xml": '<partners>\n  <partner id="P1"/>\n</partners>\n',
 "report_taxonomy.json": Path("app/ci/report_taxonomy.json").read_text(),
 "partner_order.tsv": "partner_id\trank\nP1\t1\n",
}
for k, v in files.items(): (root / k).write_text(v)
print(f"schemas={len(schemas)} edges={n} prereq_fields=8 longest_plan={layers_n+1}")
