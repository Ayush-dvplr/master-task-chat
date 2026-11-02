"""Rebuild the QC v12 DS-20 probe graph and time plan_migration on it.

    python3 -B qc_graph.py <repo_root> <variant: adv2|adv> [seed]

adv2 (QC v12.md:149-154): 1102 schemas, 5542 edges, prerequisite fields a0..a7
plus plain fields b0, b1; direct edge start->target E00001 cost 5,000,000; a
cheap zone of 1100 schemas with 5 edges each (cost 1-3: three
``lacks:a{i+1 mod 8}`` + ``add:a{i}``, one ``drop:a{i}``, one add/drop of b0/b1);
40 exits to the target requiring has:a0..has:a7, which never hold together.
adv: the same without the b0/b1 edge (8 fields, 4 zone edges each).
Run inside Docker only (common rule Always 16).
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import time
from pathlib import Path


def build(variant: str, seed: int) -> tuple[Path, str]:
    rng = random.Random(seed)
    domain = "qd"
    start, target = f"{domain}.v1", f"{domain}.v2"
    zone = [f"{domain}.v{n}" for n in range(3, 1103)]
    edges: list[tuple] = []
    count = iter(range(1, 100000))

    def edge(a, b, req, ops, cost):
        edges.append((f"E{next(count):05d}", a, b, req, ops, cost))

    edge(start, target, "", "", 5_000_000)
    edge(start, zone[0], "", "", 1)
    for a in zone:
        for _ in range(3):
            i = rng.randrange(8)
            edge(a, rng.choice(zone), f"lacks:a{(i + 1) % 8}", f"add:a{i}", rng.randint(1, 3))
        edge(a, rng.choice(zone), "", f"drop:a{rng.randrange(8)}", rng.randint(1, 3))
        if variant == "adv2":
            edge(a, rng.choice(zone), "", f"{rng.choice(['add', 'drop'])}:b{rng.randrange(2)}", rng.randint(1, 3))
    every = ";".join(f"has:a{i}" for i in range(8))
    for a in rng.sample(zone, 40):
        edge(a, target, every, "", rng.randint(1, 3))
    fields = [f"a{i}" for i in range(8)] + (["b0", "b1"] if variant == "adv2" else [])
    root = Path(tempfile.mkdtemp(prefix="qcgraph-"))
    schemas = [{"id": s, "domain": domain, "canonical": s == target} for s in [start, target, *zone]]
    (root / "schema_versions.json").write_text(json.dumps({"schemas": schemas}, indent=1), encoding="utf-8")
    (root / "migration_edges.csv").write_text(
        "edge_id,source,target,requires,operations,cost\n" + "".join(",".join(map(str, e)) + "\n" for e in edges),
        encoding="utf-8",
    )
    (root / "field_policy.tsv").write_text(
        "domain\tfield\tdefault\tfill\tnull_counts_as\n" + "".join(f"{domain}\t{f}\t1\t\t\n" for f in fields),
        encoding="utf-8",
    )
    (root / "null_semantics.ini").write_text(
        "[presence]\nexplicit_null = present\n\n[fill]\nmode = absent_only\n\n[tokens]\ndefault = NULL | N/A\n",
        encoding="utf-8",
    )
    (root / "partner_aliases.xml").write_text('<partners>\n  <partner id="P100"><alias>alpha-one</alias></partner>\n</partners>\n', encoding="utf-8")
    (root / "report_taxonomy.json").write_text(json.dumps({"categories": []}), encoding="utf-8")
    (root / "partner_order.tsv").write_text("partner_id\trank\n", encoding="utf-8")
    assert len(schemas) == 1102 and len(edges) == (5542 if variant == "adv2" else 4442), (len(schemas), len(edges))
    return root, start


def main() -> None:
    repo, variant = Path(sys.argv[1]), sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    sys.path.insert(0, str(repo / "src"))
    from migrakit.core.planner import plan_migration
    from migrakit.parser.contracts import load_contracts

    root, start = build(variant, seed)
    registry = load_contracts(root)
    began = time.perf_counter()
    plan = plan_migration(registry, start, {})
    seconds = time.perf_counter() - began
    print(json.dumps({"repo": repo.name, "variant": variant, "seed": seed, "schemas": len(registry.schemas),
                      "edges": len(registry.edges), "fields": registry.named_fields("qd"),
                      "plan": plan, "seconds": round(seconds, 3)}), flush=True)


if __name__ == "__main__":
    main()
