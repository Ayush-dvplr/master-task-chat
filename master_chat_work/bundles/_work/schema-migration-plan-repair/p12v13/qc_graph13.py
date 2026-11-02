"""DS-20 graphs for P12 v13.

`qc ROOT WIDTH LAYERS OUTDEG BYPASS` rebuilds QC v13.md:173-182 (same generator as QC's gen2.py, seed 11).
`stress ROOT N` writes N random in-limit graphs ROOT/s00..; each folder gets case.json with the payload.
"""
import json
import random
import sys
from pathlib import Path

F = [f"f{i}" for i in range(8)]
TAX = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/environment/ci/report_taxonomy.json")


def write(root, schemas, rows, null_present=True, fill="absent_only", null_counts=None):
    root.mkdir(parents=True, exist_ok=True)
    null_counts = null_counts or {}
    files = {
        "schema_versions.json": json.dumps({"schemas": schemas}),
        "migration_edges.csv": "\n".join(rows) + "\n",
        "field_policy.tsv": "domain\tfield\tdefault\tfill\tnull_counts_as\n"
        + "".join(f"d\t{f}\t1\t\t{null_counts.get(f, '')}\n" for f in F + ["g0", "g1"]),
        "null_semantics.ini": "[presence]\nexplicit_null = " + ("present" if null_present else "absent")
        + "\n\n[fill]\nmode = " + fill + "\n\n[tokens]\ndefault = NULL\n",
        "partner_aliases.xml": '<partners>\n  <partner id="P1"/>\n</partners>\n',
        "report_taxonomy.json": TAX.read_text(),
        "partner_order.tsv": "partner_id\trank\nP1\t1\n",
    }
    for k, v in files.items():
        (root / k).write_text(v)


def qc(root, width, layers_n, outdeg, bypass):
    rng = random.Random(11)
    layers = [["d.s"]] + [[f"d.l{k:02d}n{j:02d}" for j in range(width)] for k in range(layers_n)]
    schemas = [{"id": s, "domain": "d", "canonical": False} for L in layers for s in L] + [{"id": "d.t", "domain": "d", "canonical": True}]
    rows = ["edge_id,source,target,requires,operations,cost"]
    n = 0
    for here, there in zip(layers, layers[1:]):
        for a in here:
            for b in rng.sample(there, min(outdeg, len(there))):
                j = rng.randrange(8)
                n += 1
                A = F + ["g0", "g1"]
                x, y = rng.sample(A, 2)
                first = rng.choice([f"rename:{x}>{y}", f"add:{x}", f"drop:{x}", f"rename:{x}>{y}"])
                rows.append(f"E{n:05d},{a},{b},,{first};add:{F[j]};drop:{F[(j + 1) % 8]},1")
    for a in layers[-1]:
        n += 1
        rows.append(f"E{n:05d},{a},d.t,{';'.join('has:' + f for f in F)},,1")
    if bypass:
        n += 1
        rows.append(f"E{n:05d},d.s,d.t,,,100000")
    write(root, schemas, rows)
    return len(schemas), n


def random_ops(rng, k):
    A = F + ["g0", "g1"]
    ops = []
    for _ in range(k):
        kind = rng.choice(["rename", "add", "add", "drop", "drop", "cast"])
        if kind == "rename":
            x, y = rng.sample(A, 2)
            ops.append(f"rename:{x}>{y}")
        elif kind == "cast":
            ops.append(f"cast:{rng.choice(A)}:int")
        else:
            ops.append(f"{kind}:{rng.choice(A)}")
    return ops


def random_requires(rng, k):
    picks = rng.sample(F, k)
    return [f"{rng.choice(['has', 'has', 'lacks'])}:{f}" for f in picks]


def stress_one(root, seed, hard=False):
    rng = random.Random((5000 if hard else 1000) + seed)
    big = hard or seed % 4 == 0
    width = 15 if hard else rng.randint(12, 15) if big else rng.randint(3, 12)
    layers_n = 79 if hard else rng.randint(70, 79) if big else rng.randint(10, 79)
    while 1 + width * layers_n + 1 > 1200:
        layers_n -= 1
    outdeg = min(width, 5 if big else rng.randint(2, 5))
    layers = [["d.s"]] + [[f"d.l{k:02d}n{j:02d}" for j in range(width)] for k in range(layers_n)]
    schemas = [{"id": s, "domain": "d", "canonical": False} for L in layers for s in L] + [{"id": "d.t", "domain": "d", "canonical": True}]
    rows = ["edge_id,source,target,requires,operations,cost"]
    edges = []
    for here, there in zip(layers, layers[1:]):
        for a in here:
            for b in rng.sample(there, min(outdeg, len(there))):
                ops = random_ops(rng, rng.randint(1, 3))
                req = random_requires(rng, rng.choice([0, 0, 0, 1, 2]))
                edges.append((a, b, req, ops, rng.randint(1, 3)))
    back = 3 * width if hard else rng.choice([0, 0, width, 3 * width])
    flat = [s for L in layers[1:] for s in L]
    for _ in range(back):
        a = rng.choice(flat)
        k = int(a[3:5])
        lo = max(0, k - 3)
        b = rng.choice([s for L in layers[1 + lo:2 + k] for s in L])
        edges.append((a, b, random_requires(rng, rng.choice([0, 1])), random_ops(rng, rng.randint(1, 2)), rng.randint(1, 3)))
    exit_kind = rng.choice(["all8", "subset", "mixed", "subset"])
    for a in layers[-1]:
        if exit_kind == "all8" or (exit_kind == "mixed" and rng.random() < 0.5):
            req = [f"has:{f}" for f in F]
        else:
            req = random_requires(rng, rng.randint(2, 8))
        edges.append((a, "d.t", req, [], rng.randint(1, 3)))
        if hard:
            # A dear exit without prerequisites keeps every reached field state able to finish.
            edges.append((a, "d.t", [], [], rng.choice([200, 1000])))
    if rng.random() < 0.5:
        for _ in range(rng.randint(1, 3)):
            edges.append(("d.s", "d.t", random_requires(rng, rng.choice([0, 3])), [], rng.choice([500, 100000])))
    assert len(edges) <= 6000 and len(schemas) <= 1200, (len(schemas), len(edges))
    rng.shuffle(edges)
    for n, (a, b, req, ops, cost) in enumerate(edges, 1):
        rows.append(f"E{n:05d},{a},{b},{';'.join(req)},{';'.join(ops)},{cost}")
    null_present = seed % 3 != 1
    fill = "absent_or_null" if seed % 5 == 2 else "absent_only"
    null_counts = {f: rng.choice(["present", "absent"]) for f in rng.sample(F, 2)} if seed % 7 == 3 else {}
    write(root, schemas, rows, null_present, fill, null_counts)
    payload = {}
    for f in F + ["g0", "g1"]:
        pick = rng.choice(["absent", "null", "value", "value"])
        if pick != "absent":
            payload[f] = None if pick == "null" else rng.randint(0, 9)
    (root / "case.json").write_text(json.dumps({"start": "d.s", "payload": payload}))
    return len(schemas), len(edges)


if __name__ == "__main__":
    if sys.argv[1] == "adv":
        # QC layout, but every last-layer schema also has a dear exit without prerequisites,
        # so every reached field state stays live and only the joint exits are cheap.
        root, width, layers_n, outdeg, dear, null_present = Path(sys.argv[2]), *map(int, sys.argv[3:8])
        qc(root, width, layers_n, outdeg, False)
        rows = (root / "migration_edges.csv").read_text().splitlines()
        n = len(rows) - 1
        for j in range(width):
            n += 1
            rows.append(f"E{n:05d},d.l{layers_n - 1:02d}n{j:02d},d.t,,,{dear}")
        write(root, json.loads((root / "schema_versions.json").read_text())["schemas"], rows, bool(null_present))
        payload = {**{f"f{i}": (None if i % 2 else 1) for i in range(8)}, "g0": None, "g1": 1}
        (root / "case.json").write_text(json.dumps({"start": "d.s", "payload": payload}))
        print(f"{root.name} schemas={len(json.loads((root / 'schema_versions.json').read_text())['schemas'])} edges={n}")
    elif sys.argv[1] == "qc":
        root = Path(sys.argv[2])
        s, e = qc(root, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6] == "1")
        payload = {**{f"f{i}": (None if i % 2 else 1) for i in range(8)}, "g0": None, "g1": 1}
        (root / "case.json").write_text(json.dumps({"start": "d.s", "payload": payload}))
        print(f"{root.name} schemas={s} edges={e}")
    elif sys.argv[1] == "hard":
        root = Path(sys.argv[2])
        for seed in range(int(sys.argv[3])):
            s, e = stress_one(root / f"h{seed:02d}", seed, hard=True)
            print(f"h{seed:02d} schemas={s} edges={e}")
    else:
        root = Path(sys.argv[2])
        for seed in range(int(sys.argv[3])):
            s, e = stress_one(root / f"s{seed:02d}", seed)
            print(f"s{seed:02d} schemas={s} edges={e}")
