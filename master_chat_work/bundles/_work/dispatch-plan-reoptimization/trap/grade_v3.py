#!/usr/bin/env python3
"""77e8554 trap replay: grade_local variants plus the a2 agent solver and extra programs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade_local  # noqa: E402

A2 = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_dispatch-plan-reoptimization/"
          "traj_a2/job/trajectory/claude-opus-5/Run 1/artifacts/app/out/solver.py")


def main():
    tests, env, output = sys.argv[1:4]
    extra = [Path(p) for p in sys.argv[4:]]
    dest = grade_local.variants()
    programs = {"oracle": dest / "oracle.py", "agent_v0": grade_local.BUILD / "agent_v0.py"}
    programs.update({n: dest / f"{n}.py" for n in grade_local.NAMES[2:]})
    programs["a2_solver"] = A2
    for p in extra:
        programs[p.stem] = p
    data = Path(env).resolve() / "data"
    results = []
    for name, prog in programs.items():
        r = grade_local.score(Path(tests).resolve(), name, prog, data)
        results.append(r)
        print(name, r.get("score"), r.get("valid"), r.get("earned"), r.get("penalty"),
              r.get("triggered"), flush=True)
    Path(output).write_text(json.dumps(results, indent=2) + "\n")
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
