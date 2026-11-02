from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
OUT = ROOT / "20261029_schema-migration-plan-repair/harden_g37_9111ecc"
GATES = Path(sys.argv[1])
CAP = 70.0
NAMES = {
    "a6": "a6_final_repo", "a5": "a5_program", "blind": "blind_cee149a", "blind2": "blind_4f7606c",
    "tb_d721": "blind_d721", "tb_d2fb": "blind_d2fb", "opus": "first_write_opus_a4",
    "abo": "all_but_one_plain_dijkstra", "gen_astar": "astar_schema_bound",
    "gen_signature_keyed": "prerequisite_keyed", "gen_incumbent": "incumbent",
    "gen_bidirectional": "bidirectional", "gen_exhaustive": "exhaustive", "gen_greedy": "greedy",
    "gen_schema_only": "schema_only", "gen_dominance": "dominance",
}


def gate(name: str) -> dict[str, float | None]:
    found = sorted((GATES / "jobs" / name).glob("*/result.json"))
    if not found:
        return {"reward": None, "verifier_seconds": None}
    trial = json.loads(found[0].read_text())
    rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
    phase = trial.get("verifier") or {}
    start, end = phase.get("started_at"), phase.get("finished_at")
    seconds = None
    if start and end:
        seconds = round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 1)
    return {"reward": rewards.get("reward"), "verifier_seconds": seconds}


def main() -> None:
    costs = json.loads((WORK / "proto/g37_cost_summary.json").read_text())
    rows = {NAMES[key]: value for key, value in costs.items()}
    over = {name: round(row["crash_timeout_share_of_positive"], 2) for name, row in rows.items()
            if row["crash_timeout_share_of_positive"] > CAP}
    gates = {name: gate(name) for name in ("oracle-1", "oracle-2", "oracle-3", "owner-1", "nop-1", "stub-1", "forgery-1")}
    a6 = rows["a6_final_repo"]["tests_percent"]
    judge = {"low": 100 * 4 / 49, "mid": 100 * 7 / 49, "high": 100 * 13 / 49}
    worst_direct = max(row["wall_seconds"] for row in rows.values())
    harbor_seconds = [g["verifier_seconds"] for g in gates.values() if g["verifier_seconds"] is not None]
    status = "PAUSED" if over else "DONE"
    result = {
        "sha": "9111ecc", "slug": "schema-migration-plan-repair", "step": "gate37-redesign", "status": status,
        "paused_reason": (f"crash+timeout share of positive test weight above the {CAP:.0f}% cap: "
                          + ", ".join(f"{k} {v}%" for k, v in over.items())) if over else None,
        "lever": "60 held-out gated large-graph worlds 47-106 (w5, RNG 9000+n, 15 s child cap) + judge probes R21-R25 (live R19-R23)",
        "tests": 141, "criteria": 23, "lever_share": 100 * 300 / 591,
        "a6_repo_tests": a6, "a5_repo_tests": rows["a5_program"]["tests_percent"],
        "kill_table": {name: round(row["tests_percent"], 2) for name, row in rows.items()},
        "lever_points_kept": {name: 300 - row["lever_lost_points"] for name, row in rows.items()},
        "lever_loss_kind": {name: ("WRONG" if row["lever_wrong_points"] else "TIMEOUT") for name, row in rows.items()},
        "crash_timeout_share": {name: round(row["crash_timeout_share_of_positive"], 2) for name, row in rows.items()},
        "crash_timeout_share_of_lost": {name: round(row["crash_timeout_share_of_lost"], 2) for name, row in rows.items()},
        "crash_timeout_metric": "crash+timeout points / 591 positive test points (master 14:15: a5 390/591 = 65.99%)",
        "timeout_cap": CAP,
        "cost_first_write_tests": rows["first_write_opus_a4"]["tests_percent"],
        "cost_all_but_one_tests": rows["all_but_one_plain_dijkstra"]["tests_percent"],
        "blind_tests": {"cee149a": rows["blind_cee149a"]["tests_percent"], "4f7606c": rows["blind_4f7606c"]["tests_percent"],
                        "d721": rows["blind_d721"]["tests_percent"], "d2fb": rows["blind_d2fb"]["tests_percent"],
                        "9179": "skipped: identical to 4 measured blinds", "b686": "skipped: identical to 4 measured blinds"},
        "docs_changed": False, "judge_changed": True,
        "pred_judge": judge, "pred_judge_mid": judge["mid"],
        "pred_final": (a6 + judge["mid"]) / 2,
        "pred_final_range": {k: (a6 + v) / 2 for k, v in judge.items()},
        "timeout_share": max(row["crash_timeout_share_of_positive"] for row in rows.values()),
        "ref_seconds_max": 0.82, "ref_seconds_audit_300_seeds": 0.266548917, "limit_seconds": 10, "child_cap_seconds": 15,
        "verifier_worst_s": max([worst_direct, *harbor_seconds]),
        "verifier_worst_direct_s": worst_direct, "verifier_worst_direct_program": max(rows, key=lambda n: rows[n]["wall_seconds"]),
        "verifier_seconds": max([worst_direct, *harbor_seconds]), "verifier_limit_s": 2700, "verifier_bar_s": 2430,
        "harbor_gates": gates,
        "oracle": [gates[f"oracle-{i}"]["reward"] for i in (1, 2, 3)],
        "owner": gates["owner-1"]["reward"], "nop": gates["nop-1"]["reward"],
        "stub": gates["stub-1"]["reward"], "forgery": gates["forgery-1"]["reward"],
        "old_checks_changed": 0, "old_reference_calls": 987, "old_reference_calls_changed": 0,
        "xref_findings": 0, "qc_fail": 0, "validator": "40 passed, 0 failed, 0 warnings",
        "tree_sha": "ebf080b7b781", "tasks_input_tree_sha": sys.argv[2], "tasks_input_synced": sys.argv[3] == "yes",
        "report": str(OUT / "HARDEN_REPORT.md"),
    }
    (OUT / "result_9111ecc.json").write_text(json.dumps(result, indent=2) + "\n")
    print(status, json.dumps({k: result[k] for k in ("oracle", "owner", "nop", "stub", "forgery", "verifier_worst_s", "pred_final")}))


if __name__ == "__main__":
    main()
