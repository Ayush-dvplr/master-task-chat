"""Read the harbor gate trials: reward and measured verifier seconds per gate."""
import json
import sys
from datetime import datetime
from pathlib import Path

GATES = Path("/tmp/wae6740572_gate")
NAMES = ["oracle-1", "oracle-2", "oracle-3", "owner-1", "nop-1", "stub-1", "forgery-1"]


def span(phase):
    if not phase or not phase.get("started_at") or not phase.get("finished_at"):
        return None
    start = datetime.fromisoformat(phase["started_at"])
    end = datetime.fromisoformat(phase["finished_at"])
    return round((end - start).total_seconds(), 1)


def gate(name):
    found = sorted((GATES / "jobs" / name).glob("*/result.json"))
    if not found:
        return {"name": name, "reward": None, "verifier_seconds": None, "agent_seconds": None, "trial": None}
    trial = json.loads(found[-1].read_text())
    rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
    return {
        "name": name,
        "reward": rewards.get("reward"),
        "verifier_seconds": span(trial.get("verifier")),
        "agent_seconds": span(trial.get("agent_execution")),
        "exception": (trial.get("exception_info") or {}).get("exception_type"),
        "trial": found[-1].parent.name,
    }


if __name__ == "__main__":
    rows = [gate(n) for n in NAMES]
    for r in rows:
        print(json.dumps(r))
    secs = [r["verifier_seconds"] for r in rows if r["verifier_seconds"] is not None]
    print("MAX_VERIFIER", max(secs) if secs else None)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(rows, indent=2) + "\n")
