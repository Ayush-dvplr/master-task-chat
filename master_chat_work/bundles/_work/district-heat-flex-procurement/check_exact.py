"""Exactness proof for the round-1 optimisers (scratch, never shipped).

Usage: python3 check_exact.py TEST_OUTPUT_PY SOLVE_PY [count]

Builds `count` random small extracts (2 to 7 sites per event-region, 1 to 4 offers per site,
tight and loose ceilings, odd Wh values, forced ties from twin offers) and compares three
independent methods on the chosen portfolios, interval quantities and tie decisions:
  1. the round-1 verifier reference (state-merging DP, sites in descending id order),
  2. the round-1 oracle solve.py (state-merging DP, sites in ascending id order),
  3. the round-0 verifier reference (plain enumeration of every portfolio).
"""
from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "stub"))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def random_spec(m, seed: int) -> dict:
    rng = random.Random(seed)
    eid = f"X{seed:04d}"
    n = rng.randint(1, 4)
    spec = {"events": [m._event(eid, n, rng.randint(0, 3), rng.randint(0, 2))], "sites": [], "offers": [],
            "targets": {}, "limits": {}, "floors": []}
    for region in m.REGION_CODES:
        for i in range(rng.randint(2, 7)):
            sid = f"{region[0]}{i}"
            spec["sites"].append(m._site(eid, sid, code=rng.choice(m.REGION_CODES[region]), seg=rng.choice("CP"),
                                         auth=rng.random() > 0.1))
            letters = "ABCD"[:rng.randint(1, 4)]
            made = []
            for letter in letters:
                if made and rng.random() < 0.2:
                    twin = rng.choice(made)
                    o = m._offer(eid, sid, letter, twin["cost"], list(twin["r"]), list(twin["v"]))
                else:
                    unit = rng.choice([1000, 1, 5, 15])
                    o = m._offer(eid, sid, letter, rng.randint(0, 40) * 10,
                                 [rng.randint(0, 4) * unit for _ in range(n)], [rng.randint(0, 2) * unit for _ in range(n)])
                made.append(o)
                spec["offers"].append(o)
        spec["targets"][(eid, region)] = [(rng.randint(0, 8) * 1000, rng.randint(1, 3)) for _ in range(n)]
        spec["limits"][(eid, region)] = [(rng.choice([rng.randint(1, 8) * 1000 + rng.choice([0, 4, 5]), 500000]),
                                          rng.choice([rng.randint(0, 4) * 1000 + rng.choice([0, 5]), 500000]))
                                         for _ in range(n)]
        for g in "CP":
            if rng.random() < 0.6:
                spec["floors"].append((eid, region, g, rng.randint(0, 6) * 1000 + rng.choice([0, 5]), rng.randint(1, 3)))
    return spec


def view(files: dict) -> list:
    out = []
    for r in ("North", "South", "West", "East"):
        for e in files[f"region_{r}.json"]["events"]:
            out.append((r, e["selected_offer_ids"], e["intervals"]))
    return [out, files["policy_audit.json"]["tie_decisions"]]


def main() -> None:
    new = load(Path(sys.argv[1]), "t_new")
    old = load(HERE / "test_output_r0.src.py", "t_old")
    solve = sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    scratch = Path(tempfile.mkdtemp(prefix="dhfp-exact-"))
    stats = {"extracts": 0, "event_regions": 0, "ties": 0, "mismatch": 0}
    for seed in range(count):
        folder = new.write_extract(scratch / f"x{seed}", random_spec(new, seed))
        a = view(new.reference(folder))
        c = view(old.reference(folder))
        out = scratch / f"o{seed}"
        subprocess.run([sys.executable, solve, str(folder), str(out)], check=True)
        b = view({n: json.loads((out / n).read_text()) for n in new.ARTIFACT_JSON})
        stats["extracts"] += 1
        stats["event_regions"] += len(a[0])
        stats["ties"] += len(a[1])
        if not a == b == c:
            stats["mismatch"] += 1
            print("MISMATCH seed", seed)
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
