#!/usr/bin/env python3
"""Fill the HARDEN_REPORT placeholders from gates.json and write result_6740572.json.

usage: finish.py <bundle_tree_sha> <tasks_input_tree_sha> <diff_lines>
"""
import json
import sys
from pathlib import Path

OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_warrant-asof-entitlement-compiler/harden_a1")
W = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/warrant-asof-entitlement-compiler")
REPORT = OUT / "HARDEN_REPORT.md"
CAP = 2430.0

tree_after, tree_ti, diff_lines = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = {r["name"]: r for r in json.loads((W / "gate" / "gates.json").read_text())}


def reward(name):
    return rows[name]["reward"]


def f3(x):
    return "missing" if x is None else f"{x:.3f}"


def secs(name):
    x = rows[name]["verifier_seconds"]
    return "n/a" if x is None else f"{x:.1f} s"


oracle = [reward(f"oracle-{i}") for i in (1, 2, 3)]
verifier = {n: r["verifier_seconds"] for n, r in rows.items() if r["verifier_seconds"] is not None}
vmax_name = max(verifier, key=verifier.get)
vmax = verifier[vmax_name]
synced = diff_lines == 0 and tree_after == tree_ti
ok = (
    oracle == [1.0, 1.0, 1.0]
    and reward("owner-1") == 1.0
    and reward("nop-1") == 0.0
    and vmax <= CAP
    and synced
)
status = "DONE" if ok else "PAUSED"

fill = {
    "TREE_AFTER": tree_after,
    "TREE_TI": tree_ti,
    "GATE_ORACLE": " / ".join(f3(x) for x in oracle)
    + " (verifier " + " / ".join(secs(f"oracle-{i}") for i in (1, 2, 3)) + ")",
    "GATE_OWNER": f"{f3(reward('owner-1'))} (verifier {secs('owner-1')})",
    "GATE_NOP": f"{f3(reward('nop-1'))} (verifier {secs('nop-1')})",
    "GATE_STUB": f"{f3(reward('stub-1'))} (verifier {secs('stub-1')})",
    "GATE_FORGERY": f"{f3(reward('forgery-1'))} (verifier {secs('forgery-1')}); pays 46 of 152: the 13 original artifact-only checks on the shipped corpus (47 points) less negative_legacy_tool_delivered (-1); every tool rerun check pays 0. Those 13 checks were 47 of 72 positive points (65%) before the build and are 47 of 152 (31%) now. QC CL-2 watch item, OUT/QC_RISKS.md item 11",
    "HARBOR_VERIFIER": f"max {vmax:.1f} s ({vmax_name}); cap 2,430 s",
    "SYNC_RESULT": (
        f"diff -rq BUNDLE vs Tasks_INPUT is empty; both trees {tree_after}"
        if synced
        else f"diff -rq shows {diff_lines} lines; BUNDLE {tree_after}, Tasks_INPUT {tree_ti}"
    ),
}
text = REPORT.read_text()
for key, value in fill.items():
    assert key in text, key
    text = text.replace(key, value)
if status != "DONE":
    text = text.replace("): BUILD DONE\n", "): BUILD PAUSED\n", 1)
REPORT.write_text(text)

result = {
    "sha": "6740572",
    "slug": "warrant-asof-entitlement-compiler",
    "step": "harden-g37-a1-opt1-build",
    "status": status,
    "lever": "per-corpus gateway conventions (HR day clock = one corpus zone, grant start = requested) on 8 held-out conv tiers C1-C8, unique fit 1/56 each; 16 dev+prod profile checks w5",
    "tests": 152,
    "test_checks": 44,
    "criteria": 17,
    "lever_share": 52.6,
    "a1_program_tests": 47.4,
    "kill_table": {
        "a1": 47.4,
        "P0s_first_write": 47.4,
        "P2n_careful_blind": 47.4,
        "P3b_binary": 47.4,
        "P4o_all_but_one": 47.4,
        "P6o_careful_wide_reference_class": 100.0,
    },
    "kill_table_note": "P0s to P4o measured 69/152 and P6o 149/152; +3 is report_transcript_complete, a score.py artifact (its repair entry names engine.py, absent in those program folders)",
    "cost_first_write_tests": 47.4,
    "cost_all_but_one_tests": 47.4,
    "docs_changed": True,
    "judge_changed": True,
    "shipped_data_changed": True,
    "pred_judge_mid": 30.0,
    "timeout_share": 0.0,
    "pred_final": 38.7,
    "pred_final_peer_judge": 43.7,
    "ref_seconds_max": 110.5,
    "limit_seconds": 900,
    "verifier_seconds": round(max(vmax, 991.5), 1),
    "verifier_seconds_harbor": {n: round(s, 1) for n, s in verifier.items()},
    "verifier_seconds_scorepy_worst": {"P6o": 991.5, "P4o": 970.6},
    "oracle": oracle,
    "owner": reward("owner-1"),
    "nop": reward("nop-1"),
    "stub": reward("stub-1"),
    "forgery": reward("forgery-1"),
    "forgery_note": "46/152: the 13 original artifact-only checks on the shipped corpus (47 points) less negative_legacy_tool_delivered (-1); every tool rerun check 0; those checks were 47/72 (65%) before the build, 47/152 (31%) now; QC CL-2 watch",
    "xref_findings": 0,
    "precheck": "PRECHECK CLEAN",
    "validator": "39 passed, 1 failed: 7.4 negative_hardcoded_sample_answers, pre-existing on the a1 backup, reported not fixed",
    "tree_sha": tree_after,
    "tree_sha_tasks_input": tree_ti,
    "tasks_input_synced": synced,
    "report": str(REPORT),
    "risk": "a careful-wide program that searches every corpus zone clock (P6o) keeps 80/80 lever points (tests 100); the master's 3 fresh blinds decide (any > 70 or two > 65: stop before QC and ask Ayush)",
}
(OUT / "result_6740572.json").write_text(json.dumps(result, indent=2) + "\n")
json.loads((OUT / "result_6740572.json").read_text())
print("STATUS", status, "vmax", vmax, vmax_name, "oracle", oracle)
