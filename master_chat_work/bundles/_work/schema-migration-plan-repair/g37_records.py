from __future__ import annotations

import ast
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
tree = ast.parse((BUNDLE / "tests/test_output.py").read_text())
lines = {node.name: node.lineno for node in tree.body if isinstance(node, ast.FunctionDef)}
heading = "## Gate v3.7 redesign a6 (board 9111ecc)"
rows = ["| Check | Weight | Seed stream | Check body | Owned output |", "|---|---|---|---|---|"]
for number in range(47, 107):
    name = f"world_{number:02d}_core_gated_graph"
    rows.append(f"| {name} | 5 | 9000+{number} | tests/test_output.py:{lines[name]} | one record and its run summary |")
table = "\n".join(rows)
lever = f"""
{heading}

This section supersedes the unfinished a4f790c half-build above. The approved build adds 60 gated worlds (300 positive points), not 34. There are 141 registered checks, 135 positive worth 591 and six negative worth 14. New-tier share is 300/591 = 50.76%; all hidden whole-document checks together are 540/591 = 91.37%. No old check was removed or weakened.

The existing _g_core family supplies the corridor and state-changing region. _g_gate changes the region's exits to require a fourth field that only a dear entry edge establishes. Each world uses its own stream and one package call. The planted plan remains reachable and non-empty; the schema-only remainder is optimistic about exits unavailable to the current field state. The reference uses the maximum of schema and per-prerequisite-field projected remainders; it does not assume a particular solver implementation.

Rules: K14 repository_contract.md:88 (bounds and ten seconds per plan), M2 migration_semantics.md:10 (positive integer costs), M3/M4 :13/:17 (field operations), M6 :31 (current-state prerequisites), M7 :35 (revisits), M8 :41 (least cost then edge-id list), and N2-N4 null_semantics.ini:7. No doc or shipped input changed. Generator _g_gate is tests/test_output.py:{lines['_g_gate']}; reference _reference_plan is :{lines['_reference_plan']}; per-world child cap is TIME_LIMIT_SEC+5 = 15 s in :{lines['_world_holds']}.

G7: g37_guard.json records 81 old check bodies and weights unchanged; immutable input files unchanged. Docker g37_audit.log records 987 old reference calls unchanged (b0f465e55d9b6d1a), old world documents unchanged, and 300 new shape seeds. Maximum reference call was 0.267 s; maximum construction 0.319 s. Direct oracle final tests passed 591/591; real Harbor gates remain separate.

Master go at 10:05 permits CRASH+TIMEOUT loss up to 60% of positive test weight for this bundle only. The new tier alone costs 50.76% when fully lost; cumulative old-plus-new timeout weight must also be measured, not silently ignored. Final measurements live in COST_TABLE.md and proto/g37_cost_*.json. Existing kill5/kill6 blocks are ALL_DONE and were not rerun.

{table}
"""
defence = f"""
{heading}

Each row below is a separate check, not a grouped assertion or an added assertion inside an old check. Shared defence applies independently to every row.

- IN-15, IN-16, AL-1, AL-2: existing documented semantics only; every read key is a K17 record key or K18 summary key. Values are the already-declared schema IDs, positive integer costs, prerequisite strings, operations, defaults and null presence forms. K14 bounds are asserted on every generated draw.
- IN-17: instruction.md, every doc and environment byte remain frozen. No trap announcement, size hint, method word, rerun promise or new invocation rule was added.
- AL-27: held-out instances exercise the existing M6-M8/K14 requirement; no new correctness rule. All old reference outputs are identical over 987 calls.
- CL-4, TS-13, G1/G1a: the observable is the complete run output of one world, records and run summary as instruction.md:3 explicitly states. One hard record belongs to that world; no row is borrowed from another world. Whole-document equality is not several independent rubric properties.
- TS-14: the description matches exact whole-output equality. The oracle passes each row; a timed-out child fails only that row, with a printed first-difference diagnostic.
- TS-20: weight 5 is the existing core whole-document tier, not a convenience point. No old weight moved.
- TS-23: 141 checks exceeds the 35-check warning. Option A makes that a warning, not a count cap; checks are never merged to lower the count.
- TS-25, CL-2, G5: every row has one non-empty feed record and a planted reachable plan. Missing/unchanged shipped archives cannot satisfy it; the shipped planner cannot enumerate these graph paths within the declared limit. No absence-only positive outcome is graded.
- TS-26: each row has its own RNG stream, hidden contract folder, feed, reference result and submission call. No deterministic duplicate dataset or shared call is being paid twice.
- DS-22, G6: TRUTH is rendered after code and judge edits from a frozen factual baseline; SHA values and line references are refreshed by script. XREF must be clean before handoff.
- G7: old 81 function bodies/weights byte-identical, immutable files identical, 987 old calls identical. Frozen snapshot is WORK/before_g37, not the a4f790c half-build.

Safe fallback for each row: retain its owned instance and exact comparison; repair a demonstrated generator defect while preserving frozen checks. Do not merge, raise weights, weaken an assertion, add a method hint, or silently waive the measured timing/share bars. If the approved design cannot meet a bar, record PAUSED rather than attempt a third design.

{table}

Judge changes are only R5/R13 removal and R21-R25 addition. JUDGE_MAP.md gives every doc sentence and actual oracle witness. New probes grade one P-h/P-d act each, never a required malformed-input output, a method, a numeric figure, or a second deliverable. J3 honesty negatives and J4 code quality remain unchanged. Oracle printed all five witnesses in Docker; G5 earns none for doing nothing.
"""
for name, section in (("LEVERS.md", lever), ("QC_DEFENCE.md", defence)):
    path = WORK / name
    text = path.read_text()
    assert heading not in text, name
    path.write_text(text.rstrip() + "\n\n" + section.strip() + "\n")
print("Recorded 60 individually owned checks in LEVERS and QC_DEFENCE")
