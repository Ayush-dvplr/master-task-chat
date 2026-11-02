"""P12 r5 trap survival: score the reflex replay and the 31 single-lever variants on one tests file.

    python3 score_r5.py LABEL TEST_OUTPUT_FILE

Oracle app: the bundle's environment plus solution/solve.py (local, APP_ROOT scratch).
Variants: measure_variants.py definitions (shipped, GROUPS, F15 cli, INLINE).
Reflex: harden_r1 agent_program/replay.py (not edited). Writes trap/r5_<LABEL>.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TRAP = Path(__file__).resolve().parent
WORK = TRAP.parent
sys.path.insert(0, str(WORK))
import make_shipped as ms  # noqa: E402
import measure_variants as mv  # noqa: E402
from verify_visible import GROUPS, tree  # noqa: E402

BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
REPLAY = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/harden_r1/agent_program/replay.py")
RUN = WORK / "run_checks.py"


def grade(app: Path, tests: Path, dest: Path) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TEST_OUTPUT_FILE=str(tests))
    p = subprocess.run([sys.executable, str(RUN), str(app), str(dest)], env=env, capture_output=True, text=True, timeout=1800)
    if p.returncode or not dest.exists():
        return {"error": p.stderr[-800:], "exit": p.returncode}
    d = json.loads(dest.read_text())
    return {"earned": d["earned"], "positive": d["positive"], "loss": d["positive"] - d["earned"],
            "failed": sorted(k for k, v in d["checks"].items() if v["weight"] > 0 and not v["pass"]),
            "negatives_fired": sorted(k for k, v in d["checks"].items() if v["weight"] < 0 and v["pass"])}


def main() -> None:
    label, tests = sys.argv[1], Path(sys.argv[2]).resolve()
    root = TRAP / f"r5_scratch_{label}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    oracle = root / "oracle"
    (oracle / "out").mkdir(parents=True)
    shutil.copytree(BUNDLE / "environment" / "repo", oracle / "repo")
    shutil.copytree(BUNDLE / "environment" / "ci", oracle / "ci")
    env = dict(os.environ, APP_ROOT=str(oracle), PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable, str(BUNDLE / "solution" / "solve.py")], env=env, check=True, capture_output=True, timeout=1800)
    out = TRAP / f"r5_{label}.json"
    results: dict = {"tests_file": str(tests)}
    results["oracle"] = grade(oracle, tests, root / "res.json")
    print("oracle", results["oracle"].get("loss"), flush=True)
    replay_app = root / "replay"
    subprocess.run([sys.executable, str(REPLAY), str(BUNDLE), str(replay_app)], env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                   check=True, capture_output=True, timeout=1800)
    results["replay"] = grade(replay_app, tests, root / "res.json")
    print("replay", results["replay"].get("earned"), flush=True)
    for name in ["shipped", *GROUPS, "F15 cli", *mv.INLINE]:
        src = root / "tree"
        if src.exists():
            shutil.rmtree(src)
        if name == "shipped":
            shutil.copytree(ms.SHIPPED, src)
        elif name in GROUPS or name == "F15 cli":
            tree(src, GROUPS.get(name, [16]))
        else:
            mv.inline(name, src)
        mv.package(src, oracle, root / "app", add_main=name not in ("shipped", "F15 cli"))
        results[name] = grade(root / "app", tests, root / "res.json")
        print(name, results[name].get("loss"), flush=True)
        out.write_text(json.dumps(results, indent=1))
    out.write_text(json.dumps(results, indent=1))
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
