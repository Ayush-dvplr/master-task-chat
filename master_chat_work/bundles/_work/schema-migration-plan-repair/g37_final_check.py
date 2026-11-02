from __future__ import annotations

import ast
import json
import math
import tomllib
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
OUT = ROOT / "20261029_schema-migration-plan-repair/harden_g37_9111ecc"


def main() -> None:
    result = json.loads((OUT / "result_9111ecc.json").read_text())
    costs = json.loads((WORK / "proto/g37_cost_summary.json").read_text())
    judge = tomllib.loads((BUNDLE / "tests/judge.toml").read_text())
    assert result["status"] == "PAUSED"
    assert result["tests"] == 141
    assert result["criteria"] == len(judge["criterion"]) == 23
    assert sum(max(c["weight"], 0) for c in judge["criterion"]) == 49
    assert math.isclose(result["a6_repo_tests"], costs["a6"]["tests_percent"])
    assert math.isclose(result["a5_repo_tests"], costs["a5"]["tests_percent"])
    shares = result["crash_timeout_share"]
    assert result["timeout_cap"] == 70 and math.isclose(result["timeout_share"], max(shares.values()), abs_tol=0.01)
    assert [k for k, v in shares.items() if v > 70] == ["exhaustive"]
    assert math.isclose(result["lever_share"], 100 * 300 / 591)
    assert math.isclose(result["pred_judge_mid"], 100 * 7 / 49)
    assert math.isclose(result["pred_final"], (result["a6_repo_tests"] + result["pred_judge_mid"]) / 2)
    assert result["pred_final"] <= 35 and result["a6_repo_tests"] <= 60
    assert all(v <= 65 for v in result["blind_tests"].values() if isinstance(v, float))
    assert max(c["wall_seconds"] for c in costs.values()) == result["verifier_worst_s"] <= 2430
    assert result["oracle"] == [1.0, 1.0, 1.0] and result["owner"] == 1.0 and result["nop"] == 0.0
    assert all(g["verifier_seconds"] <= 2430 for g in result["harbor_gates"].values())
    assert result["tasks_input_synced"] is False
    assert result["docs_changed"] is False
    assert result["judge_changed"] is True
    assert result["report"] == str(OUT / "HARDEN_REPORT.md")
    for name in ("g37_audit", "g37_solve", "g37_cost_a6", "g37_cost_a5", "g37_chainA2", "g37_chainB"):
        assert "ALL_DONE" in (WORK / "proto" / f"{name}.log").read_text()
    assert (OUT / "precheck.log").read_text().splitlines()[-1] == "PRECHECK CLEAN"
    assert "0 findings" in (OUT / "xref.log").read_text()
    assert "40 passed, 0 failed, 0 warnings" in (OUT / "validator.log").read_text()
    for name in ("TRIP.md", "DESIGN.md", "STACKING_CHECK.md", "HARDEN_REPORT.md"):
        text = (OUT / name).read_text()
        assert text.isascii(), name
        lessons = text.split("## Lessons for the master")
        assert len(lessons) == 2, name
        assert len([line for line in lessons[1].splitlines() if line.strip()]) <= 5, name
        if name == "DESIGN.md":
            assert len(text.splitlines()) <= 150
    assert not list(BUNDLE.rglob("__pycache__"))
    assert not list(BUNDLE.rglob("*.pyc"))
    for path in WORK.glob("g37_*.py"):
        ast.parse(path.read_text(), filename=str(path))
    for path in (BUNDLE / "tests/test_output.py", BUNDLE / "solution/solve.py"):
        ast.parse(path.read_text(), filename=str(path))
    print("FINAL CHECK PASS: JSON arithmetic, report limits, completed logs, static gates, AST and clean bundle")


if __name__ == "__main__":
    main()
