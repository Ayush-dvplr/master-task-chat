from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

WORK = Path("/w")
sys.path.insert(0, str(WORK / "rewardkit_stub"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    old = load("frozen_g37", WORK / "g37_frozen.src.py")
    new = load("current_g37", WORK / "test_output.src.py")
    original = old._reference_plan
    calls = 0
    digest = hashlib.sha256()

    def compared(spec, start, payload):
        nonlocal calls
        a, b = original(spec, start, payload), new._reference_plan(spec, start, payload)
        assert a == b, f"PAUSED: old reference call differs: {start}"
        calls += 1
        return a

    old._reference_plan = compared
    for name in old.WORLDS:
        a = old._world_expected(name)
        b = new._world_expected(name)
        assert a == b, f"PAUSED: old world differs: {name}"
        digest.update(json.dumps(a, sort_keys=True).encode())
    for name in old.LADDERS:
        a, b = old.case_ladder(name)[2], new.case_ladder(name)[2]
        assert a == b
        digest.update(json.dumps(a).encode())
    assert calls == 987, calls
    print("OLD_CALLS", calls, "diff=0", digest.hexdigest()[:16], flush=True)
    max_build = max_ref = 0.0
    for number in range(1001, 1301):
        start = time.perf_counter()
        world = new._World(100 + number - 1, ("CORE", "GATE"))
        new._g_gate(world, number)
        spec, lines, *_ = world.finish()
        built = time.perf_counter() - start
        assert len(lines) == 1
        assert len(spec.schemas) <= 1200 and len(spec.edges) <= 6000
        start = time.perf_counter()
        plan = new._reference_plan(spec, lines[0]["schema"], lines[0]["payload"])
        seconds = time.perf_counter() - start
        assert plan and len(plan) <= 80 and seconds <= 2.5
        max_build, max_ref = max(max_build, built), max(max_ref, seconds)
        if number % 25 == 0:
            print("SEEDS", number - 1000, "max_build", round(max_build, 3), "max_ref", round(max_ref, 3), flush=True)
    result = {"old_calls": calls, "old_call_changes": 0, "old_world_changes": 0,
              "expected_digest": digest.hexdigest()[:16], "seeds": 300,
              "max_build_seconds": max_build, "max_reference_seconds": max_ref}
    (WORK / "proto/g37_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print("ALL_DONE", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
