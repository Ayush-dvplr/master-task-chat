# TRIP: schema-migration-plan-repair, board 9111ecc

## Step 1a Answer

The a6 agent defeated the previous schema-bound worlds by implementing the same schema-graph remainder used by the test reference. Its exact A* tracks every named field, preserves state-changing revisits, and reconstructs the minimum-cost, lexicographically first edge list. The accepted redesign changes the instances, not the migration rules: a prerequisite field prevents cheap exits from a large region. The reference and oracle use an additional per-field projection remainder. The observed a6 loss is TIMEOUT, not an incorrect returned plan.

Source run: `master_chat_work/20261028_schema-migration-plan-repair/gate_run_a6/trajectory/claude-opus-5/Run 1`. Frozen result: tests 291/291 = 100%, rubric 11/38 = 28.95%, final 64.47%. Its original read-out is `gate_run_a6/TRIP.md`. The complete trajectory was inspected by step and command, never printed whole.

## Trajectory Map

Logical judge IDs refer to the approved design. Live IDs were mechanically renumbered R1-R23 because the QC kit requires a consecutive sequence; criterion names and oracle witness labels retain logical IDs.

| Evidence | Observation | Requirement | Check / Logical Criterion | Classification |
|---|---|---|---|---|
| a6 planner and final reply | Exact A* uses schema-only remainder | repository_contract.md:88, migration_semantics.md:31 | world_47_core_gated_graph through world_106_core_gated_graph | LOST_GRADED by hidden-scale TIMEOUT |
| a6 step 66 | Damaged receipt and partner-rejected-line probes performed | repository_contract.md:78, repository_contract.md:101 | R1, R2 | Earned, retained |
| a6 step 66 | No malformed line naming an existing manifest batch | repository_contract.md:95 | R3 | SKIPPED, retained |
| a6 probe commands | No spaced null-token witness | null_semantics.ini:20 | R4 | SKIPPED, retained |
| original judge result | Extra rejected-batch receipt point shares the R2 setup | repository_contract.md:78 | R5 | EASY, removed |
| a6 graph timings | Constructed graphs below 1,000 schemas | repository_contract.md:88 | R6 | SKIPPED, retained |
| a6 step 39 | Separate exhaustive comparison uses shipped contracts | migration_semantics.md:41 | R7 | SKIPPED, retained |
| a6 constructed folders | No exercised edge costing over one million | migration_semantics.md:10 | R8 | SKIPPED, retained |
| a6 step 66 | Extra ignored.txt without original-versus-copy comparison | repository_contract.md:22 | R9 | SKIPPED, retained |
| a6 step 66 | Every custom manifest batch has an admitted feed line | repository_contract.md:84 | R10 | SKIPPED, retained |
| a6 CLI commands | Output directories are fresh | repository_contract.md:54 | R11 | SKIPPED, retained |
| a6 altered-input commands | No shipped-copy used-edge cost change and rerun | repository_contract.md:34 | R12 | SKIPPED, retained |
| a6 help invocation | Help command performed | repository_contract.md:58 | R13 | EASY, removed |
| delivered a6 archive | Private helpers are called | Retained J4 code-quality criterion | R14 | Earned, retained |
| all a6 command steps | No declared contract file removed from a copied folder | repository_contract.md:18 | R21, live R19 | SKIPPED, new P-h probe |
| all a6 command steps | No run with an entirely empty feed file | repository_contract.md:95 | R22, live R20 | SKIPPED, new P-h probe |
| all a6 command steps | No copied edge-cost cell replaced with non-integer text | migration_semantics.md:10 | R23, live R21 | SKIPPED, new P-h probe |
| all a6 command steps | No shipped contract copy with one changed policy row | null_semantics.ini:11 | R24, live R22 | SKIPPED, new P-d probe |
| all a6 command steps | No shipped contract copy with changed explicit_null | null_semantics.ini:7 | R25, live R23 | SKIPPED, new P-d probe |

These observations do not establish a wrong a6 output outside the graded worlds, and no WRONG_UNGRADED or FALSE_CLAIM is invented. Existing honesty negatives and J4 remain semantically unchanged. The a6-graded prediction is R1 + R2 + R14 = 7/49 = 14.29%; this is a manual prediction, not a fresh judge run. Peer-25% sensitivity is 13/49 = 26.53%.

## New Oracle Evidence

`WORK/proto/g37_solve.log` contains ALL_DONE, all five new `check Rxx ok` witnesses, and direct authoring-runner score 591/591. R21 reports the removed schema_versions.json; R22 reports zero records; R23 names migration_edges.csv for the invalid integer; R24 changes tickets_trade.amount on line 1155; R25 changes an explicit-null record on line 753. `WORK/JUDGE_MAP.md` records each live ID, document sentence, solve.py line, and distinctness defence. These are measured oracle acts, not real Harbor reward-gate results.

## Harbor Gates And Judge Prediction (29 Oct 18:45)

Real Harbor 0.24 gates from live-kit exe_copy copies: oracle 1.0 x3 (verifier 117-123 s), owner-only 1.0, nop 0.0,
stub 0.0017, forgery 0.0102 (2,118.9 s). Judge prediction on the a6 trajectory: low 4/49 = 8.16 (R1, J4 only),
mid 7/49 = 14.29 (R1, R2, J4 as graded), high 13/49 = 26.53 (probes at the 25% peer rate). Finals with a6 tests 49.24:
28.70 / 31.76 / 37.88.

## Lessons for the master
An exact solver can miss the runtime contract without returning a wrong plan | no change: existing K14 states the runtime.
Count inherited timeout weight when applying a bundle-wide cap | template_change: _COMMON_RULES_v5.md:49, clarify cumulative versus new-tier accounting.
