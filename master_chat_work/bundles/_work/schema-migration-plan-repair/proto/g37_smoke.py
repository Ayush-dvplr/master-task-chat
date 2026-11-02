"""Smoke test: each generic variant against the oracle planner on 300 shipped feed records."""

import importlib
import json
import shutil
import sys
import time
from pathlib import Path

VARIANTS = ["astar", "signature_keyed", "dominance", "incumbent", "greedy", "exhaustive", "bidirectional", "schema_only"]
src = Path("/tmp/smoke/src")
shutil.copytree("/w/repo_fixed/src", src)
shutil.copy("/w/proto/abo_planner.py", src / "migrakit/core/abo.py")
template = Path("/w/proto/g37_generic_planner.py").read_text()
for v in VARIANTS:
    (src / f"migrakit/core/gen_{v}.py").write_text(template.replace('VARIANT = "astar"', f'VARIANT = "{v}"'))
sys.path.insert(0, str(src))
from migrakit.core.planner import plan_migration as oracle
from migrakit.parser.contracts import load_contracts

registry = load_contracts("/b/environment/ci")
lines = [json.loads(x) for x in Path("/b/environment/ci/partner_batches.jsonl").read_text().splitlines()[:300]]


def run(fn, doc):
    try:
        return fn(registry, doc["schema"], doc["payload"])
    except Exception as exc:
        return f"{type(exc).__name__}"


expected = [run(oracle, d) for d in lines]
for name in ["abo"] + [f"gen_{v}" for v in VARIANTS]:
    fn = importlib.import_module(f"migrakit.core.{name}").plan_migration
    start = time.monotonic()
    got = [run(fn, d) for d in lines]
    diff = sum(a != b for a, b in zip(got, expected))
    print("SMOKE", name, "diff", diff, "of", len(lines), "sec", round(time.monotonic() - start, 2), flush=True)
print("ALL_DONE")
