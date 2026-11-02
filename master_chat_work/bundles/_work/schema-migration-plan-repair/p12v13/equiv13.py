"""DS-20 v13 equivalence: v12 oracle planner and the goal-set planner on every reference call of the
current tests (1109), of the frozen g37 tests (987 old calls) and of gate seeds 1001..1300.

collect: run the current tests' world, ladder and plan-case builders, record every
(spec, start, payload) the reference planner sees, write each spec as a contract folder.
run <repo>: plan every recorded case with that repo's plan_migration.
compare: identical plans or error codes, plus timings.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("/w")
OUT = Path("/w/p12v13/eq")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def folder_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.iterdir()):
        h.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


def collect() -> None:
    sys.path.insert(0, str(WORK / "rewardkit_stub"))
    new = load("current_tests", WORK / "test_output.src.py")
    original = new._reference_plan
    cases: list[dict] = []
    folders: dict[str, str] = {}

    def recorded(spec, start, payload, *rest):
        root = spec.write()
        digest = folder_digest(root)
        folders.setdefault(digest, str(root))
        expected = original(spec, start, payload, *rest)
        cases.append({"folder": folders[digest], "start": start, "payload": pickle.dumps(payload),
                      "expected": expected, "where": where})
        return expected

    new._reference_plan = recorded
    where = ""
    for name in new.WORLDS:
        where = name
        new._world_expected(name)
    for name in new.LADDERS:
        where = name
        new.case_ladder(name)
    for build in ("case_revisit", "case_tie_first_edge"):
        where = build
        spec, job, expected = getattr(new, build)()
        recorded(spec, job["schema"], job["payload"])
    old = load("frozen_g37", WORK / "g37_frozen.src.py")
    frozen = old._reference_plan

    def recorded_old(spec, start, payload, *rest):
        root = spec.write()
        digest = folder_digest(root)
        folders.setdefault(digest, str(root))
        expected = frozen(spec, start, payload, *rest)
        cases.append({"folder": folders[digest], "start": start, "payload": pickle.dumps(payload),
                      "expected": expected, "where": "g37:" + where})
        return expected

    old._reference_plan = recorded_old
    for name in old.WORLDS:
        where = name
        old._world_expected(name)
    for name in old.LADDERS:
        where = name
        old.case_ladder(name)
    for number in range(1001, 1301):
        world = new._World(100 + number - 1, ("CORE", "GATE"))
        new._g_gate(world, number)
        spec, lines, *_ = world.finish()
        where = f"seed_{number}"
        recorded(spec, lines[0]["schema"], lines[0]["payload"])
    OUT.mkdir(exist_ok=True)
    (OUT / "cases.pkl").write_bytes(pickle.dumps(cases))
    print("COLLECT", len(cases), "cases", len(folders), "folders", flush=True)


def run(repo: str, tag: str) -> None:
    sys.path.insert(0, str(Path(repo) / "src"))
    from migrakit.core.planner import plan_migration
    from migrakit.errors import MigrationError
    from migrakit.parser.contracts import load_contracts

    cases = pickle.loads((OUT / "cases.pkl").read_bytes())
    registries: dict[str, object] = {}
    results = []
    for case in cases:
        folder = case["folder"]
        if folder not in registries:
            registries[folder] = load_contracts(Path(folder))
        payload = pickle.loads(case["payload"])
        start = time.perf_counter()
        try:
            plan = plan_migration(registries[folder], case["start"], payload)
        except MigrationError as error:
            plan = "ERROR:" + str(getattr(error, "code", error))
        results.append({"plan": plan, "seconds": time.perf_counter() - start, "where": case["where"]})
    (OUT / f"{tag}.json").write_text(json.dumps(results))
    print("RUN", tag, len(results), flush=True)


def compare() -> None:
    cases = pickle.loads((OUT / "cases.pkl").read_bytes())
    old = json.loads((OUT / "old.json").read_text())
    new = json.loads((OUT / "new.json").read_text())
    differ = [i for i, (a, b) in enumerate(zip(old, new)) if a["plan"] != b["plan"]]
    vs_reference = [i for i, (c, b) in enumerate(zip(cases, new))
                    if c["expected"] is not None and b["plan"] != c["expected"]]
    gate = [i for i, c in enumerate(cases) if c["where"].startswith("world_") and 47 <= int(c["where"].split("_")[1]) <= 106]
    groups = {"current": [i for i, c in enumerate(cases) if not c["where"].startswith(("g37:", "seed_"))],
              "g37_old": [i for i, c in enumerate(cases) if c["where"].startswith("g37:")],
              "seeds": [i for i, c in enumerate(cases) if c["where"].startswith("seed_")]}
    worlds = sorted({c["where"] for c in cases})
    result = {
        "cases": len(cases), "sources": len(worlds), "groups": {k: len(v) for k, v in groups.items()},
        "gate_cases": len(gate), "gate_worlds": len({cases[i]["where"] for i in gate}),
        "old_new_plan_differences": len(differ), "new_vs_reference_differences": len(vs_reference),
        "max_old_seconds": max(r["seconds"] for r in old), "max_new_seconds": max(r["seconds"] for r in new),
        "max_old_gate_seconds": max((old[i]["seconds"] for i in gate), default=0.0),
        "max_new_gate_seconds": max((new[i]["seconds"] for i in gate), default=0.0),
        "sum_old_seconds": sum(r["seconds"] for r in old), "sum_new_seconds": sum(r["seconds"] for r in new),
        "first_differences": [{"where": cases[i]["where"], "old": old[i]["plan"], "new": new[i]["plan"]} for i in differ[:5]],
    }
    (WORK / "p12v13/equiv.json").write_text(json.dumps(result, indent=2) + "\n")
    print("ALL_DONE", json.dumps(result), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "collect":
        collect()
    elif mode == "run":
        run(sys.argv[2], sys.argv[3])
    elif mode == "compare":
        compare()
    elif mode == "all":
        collect()
        for repo, tag in (("/w/p12v13/repo_v12", "old"), ("/w/repo_fixed", "new")):
            subprocess.run([sys.executable, "-B", __file__, "run", repo, tag], check=True)
        compare()
