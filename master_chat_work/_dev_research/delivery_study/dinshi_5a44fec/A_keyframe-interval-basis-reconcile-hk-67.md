# A keyframe-interval-basis-reconcile-hk-67

**Verdict: PARTLY** (one genuine misreading, amplified by one named gate across many tests)

Recorded: overall 56.2 / tests 26.85 / rubric 85.56. Positive test weight 108, failed 79, passed 29 (29/108 = 26.85).

## Run health
- result.json `exception_info` null; agent ran 09:47:32-09:56:50 UTC (9 min, 25 steps). No negative fired (all 6 negatives `passed:false`). ctrf failure messages empty. All 14 artifacts present under `artifacts/app/out/`.
- No crash, path or permission artefact. Every failure is a wrong value or a gate.

## Root cause (wrong value)
- Expected durable values (tests/test_output.py:67 `EXPECTED["values"]`): caption-main 1449, credits-roll 1579, main-program 1796. Agent `normalized.jsonl`: caption-main 1763, credits-roll 1600, main-program 1220. All other 8 values equal.
- Rule: instruction.md:9 "Where two authority records amend the same render track inside a single generation, decide from the evidence which of the two the durable state carries, because their recorded order settles nothing." Oracle settles by `precedence = (effective_generation, 1 if recorded_by == "authority-service" else 0, seq)` (solution/solve.py:94-96). No data or policy file states that authority-service wins (grep for `recorded_by|authority-service|migration-service` in md/json data: no hit outside the ledger). The only evidence is one pair inside the conformance cohort (preview-reel seq 18 vs 19, interval_conformance_fixtures.json `reference_cohort`).
- Agent step 7 (09:53:02): "preview-reel conflict seq18 (1897, authority) vs seq19 (1363, migration) ... Cohort digest ... → seq 18 stands" — correct. Then "Rollbacks: after js10 surviving set ... [..., 29 main, 30 credits]; pos11=credits-roll(30)→restore 1579(seq28); then ... pos10=credits-roll(28)→restore 1600(seq15)". It never treated credits-roll seq 28 (authority) vs seq 30 (migration), same generation 44, as competing; its `settle_conflicts` resolves non-cohort conflicts by `max(recs, key=seq)` (agent transform.py:101-103) — the recorded order the instruction says settles nothing.
- Cascade: the positional rollbacks (interval_authority_policy.md:36-46, target_position against surviving set) then hit credits-roll twice instead of main-program and caption-main. One settlement decision moves 3 values, the digest (60619 vs 61038), weights, ranks, preserved set and every reproducer run.
- Separate genuine slips: `pre_repair_divergence_count` 3 vs 5; `transition_order` lists rebuild_interval_index twice (7 items vs 6); `rejected_hypothesis.falsified_by_transition` rebuild_interval_index vs expected `transitions[4]` replay_encode_journal.

## Gate (amplifier)
- `_replay_landed` (tests/test_output.py:298-305) returns None unless credits-roll == 1579; comment at 271-279 states the design: "Every other recovery claim rides on `_replay_landed` ... the settled 1579 appears in no shipped file."
- Tests failed **only** by the gate (agent's own field equals expected; checked against artifacts): report_preserves_retired_record 3, resolution_dependency_order 3 (agent list == `EXPECTED["dependency_order"]`), report_minimal_delta 5 (agent seq 20 == focal_seq), verdict_authority_anchored_post_replay 5, verdict_zero_post_repair_divergence 3, partition_cover_is_disjoint 3 (INFERRED: partition_values_match_core passed). = **22 points**.
- Is the gate stated? The rule it encodes is stated only as "decide from the evidence"; the winning criterion is induced from one cohort pair. Gate intent is in test comments, not in the instruction.

## Points
- Lost 79: 22 gate-only + 57 wrong-value (core 5, metrics 5+5+3, reproducer 5+5, composed 3x5, preserved set 5, rejected hypothesis 5, pre-count 3, transition order 1). All genuine in the sense that the gating value itself is wrong; 22 are amplification.
- Lever shape: same-generation tie settled by a rule witnessed once in a cohort and never stated (HIDDEN-RULE candidate, "implied by a single witnessed case"), amplified by positional rollback and a value gate.
