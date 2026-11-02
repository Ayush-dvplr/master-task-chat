"""P3 method (b): score solvers with the REAL tests/test_output.py under rewardkit 0.2.1.

Builds the exe_copy tests-only copy of BUNDLE (judge removed, test channel renormalised
to 1 / positive total), builds its tests image, then for every solver:
  1. writes /app/out on the host by running the solver as derive_report.py on the
     shipped data (S0 nop writes nothing, S1 stub writes the exe_copy stub artifacts),
  2. runs tests/test.sh in the tests image with that /app mounted (as playground does),
  3. records reward.json and every criterion value from reward-details.json.

Usage: python3 score_p3.py BUNDLE SCRATCH OUT_JSON solver_id=path [solver_id=path ...]
  path may be NOP or STUB.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

QC = Path("/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC")


def sh(*cmd: str, check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check, timeout=timeout)


def criteria_values(details) -> dict[str, float]:
    found: dict[str, float] = {}
    if isinstance(details, dict):
        name, value = details.get("name"), details.get("value", details.get("score"))
        if isinstance(name, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
            found[name] = value
        for item in details.values():
            found.update(criteria_values(item))
    elif isinstance(details, list):
        for item in details:
            found.update(criteria_values(item))
    return found


def main() -> None:
    bundle, scratch, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    solvers = dict(a.split("=", 1) for a in sys.argv[4:])
    scratch.mkdir(parents=True, exist_ok=True)
    copy = scratch / "tests-only"
    if not copy.exists():
        sh(sys.executable, str(QC / "exe_copy.py"), str(bundle), str(copy))
    tag = f"dhfp-p3-tests:{scratch.name.lower()}"
    sh("docker", "build", "-q", "-t", tag, str(copy / "tests"), timeout=900)
    artifacts = tomllib.loads((bundle / "task.toml").read_text())["artifacts"]
    data = bundle / "environment" / "data"
    results = json.loads(out_json.read_text()) if out_json.exists() else {}
    for sid, path in solvers.items():
        app = scratch / f"app-{sid}"
        logs = scratch / f"logs-{sid}"
        shutil.rmtree(app, ignore_errors=True)
        shutil.rmtree(logs, ignore_errors=True)
        (app / "out").mkdir(parents=True)
        logs.mkdir()
        agent_rc = None
        if path == "STUB":
            for a in artifacts:
                p = app / Path(a).relative_to("/app")
                p.write_text("{}\n" if a.endswith(".json") else "")
        elif path != "NOP":
            prog = app / "out" / "derive_report.py"
            shutil.copy(path, prog)
            agent_rc = sh(sys.executable, str(prog), str(data), str(app / "out"), check=False, timeout=900).returncode
        grade = sh("docker", "run", "--rm", "--network", "none", "-v", f"{app}:/app", "-v", f"{logs}:/logs",
                   tag, "bash", "/tests/test.sh", check=False, timeout=2700)
        reward_file = logs / "verifier" / "reward.json"
        details_file = logs / "verifier" / "reward-details.json"
        reward = json.loads(reward_file.read_text())["reward"] if reward_file.is_file() else None
        values = criteria_values(json.loads(details_file.read_text())) if details_file.is_file() else {}
        results[sid] = {"solver": path, "agent_rc": agent_rc, "reward": reward, "criteria": values,
                        "verifier_tail": None if reward is not None else (grade.stdout + grade.stderr)[-1500:]}
        out_json.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
        print(sid, "reward", reward, "agent_rc", agent_rc, flush=True)
    sh("docker", "rmi", "-f", tag, check=False)


if __name__ == "__main__":
    main()
