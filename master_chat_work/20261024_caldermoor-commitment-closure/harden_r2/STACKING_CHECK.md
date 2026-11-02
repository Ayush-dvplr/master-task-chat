# STACKING_CHECK caldermoor-commitment-closure (593ecae harden r2, LEVER_RULES section 5)

Tool: `master_chat_tasks/tools/stacking_check.py` on the bundle: 49 checks, 162 positive test points, negatives -21; judge 12 criteria, +22/-12, batched. Its static class hints are corrected by hand below (the tool reads names and docstrings, not which seed a test runs on). Reflex column = the probe-1 agent's final program (`OUT/agent_program/reconcile.py`) under the new tests, local scorer (oracle 162/162, nop 0/162).

## (a) One row per positive test

| test | w | observable | decisive logic | levers whose misread fails it | reflex program |
|---|---|---|---|---|---|
| normalized_and_rejects_exact | 2 | normalized_assertions.jsonl, rejects.csv (shipped) | reject table order, units, day shift | none | pass |
| normalized_and_rejects_hard | 5 | normalized_assertions.jsonl, rejects.csv (unseen eval seed) | reject table order, units, day shift | none | pass |
| commitment_ledger_exact | 2 | commitment_ledger.jsonl (shipped) | resolved state, class, allocated_minutes | none | FAIL |
| commitment_ledger_hard | 5 | commitment_ledger.jsonl (unseen eval seed) | resolved state, class, allocated_minutes | A, B, C | FAIL |
| alias_resolution_exact | 2 | alias_resolution.jsonl (shipped) | half-open alias scopes | none | pass |
| alias_resolution_hard | 5 | alias_resolution.jsonl (unseen eval seed) | half-open alias scopes | none | pass |
| actor_roster_exact | 2 | actor_roster.csv (shipped) | waivers_granted/lapsed per principal | none | FAIL |
| actor_roster_hard | 5 | actor_roster.csv (unseen eval seed) | waivers_granted/lapsed per principal | C | FAIL |
| project_lineage_exact | 2 | project_lineage.csv (shipped) | rename scope, allocated sum | none | FAIL |
| project_lineage_hard | 5 | project_lineage.csv (unseen eval seed) | rename scope, allocated sum | A, B, C | FAIL |
| state_resolution_and_contests_exact | 2 | state_resolution.csv, assertion_contests.csv (shipped) | precedence, reversal | none | pass |
| state_resolution_and_contests_hard | 5 | state_resolution.csv, assertion_contests.csv (unseen eval seed) | precedence, reversal | none | pass |
| edge_partition_exact | 2 | live_edges.csv, dropped_edges.csv (shipped) | edge scope, dependent_blocked | none | FAIL |
| edge_partition_hard | 5 | live_edges.csv, dropped_edges.csv (unseen eval seed) | edge scope, dependent_blocked | A | FAIL |
| closure_and_blocked_exact | 2 | blocking_closure.jsonl, blocked_commitments.csv (shipped) | blocked predicate, closure, allocated | none | FAIL |
| closure_and_blocked_hard | 5 | blocking_closure.jsonl, blocked_commitments.csv (unseen eval seed) | blocked predicate, closure, allocated | A, B, C | FAIL |
| queues_and_registers_exact | 2 | actionable/deferred/withdrawn/unresolvable (shipped) | classes, allocated_minutes | none | FAIL |
| queues_and_registers_hard | 5 | actionable/deferred/withdrawn/unresolvable (unseen eval seed) | classes, allocated_minutes | A, B, C | FAIL |
| cadence_and_waiver_exact | 2 | cadence_debt.csv, waiver_trace.jsonl (shipped) | first-match walk, allowance | none | FAIL |
| cadence_and_waiver_hard | 5 | cadence_debt.csv, waiver_trace.jsonl (unseen eval seed) | first-match walk, allowance | B, C | FAIL |
| allocation_and_load_exact | 2 | attention_allocation.csv, month_load_index.csv (shipped) | reserve, largest remainder, floor | none | FAIL |
| allocation_and_load_hard | 5 | attention_allocation.csv, month_load_index.csv (unseen eval seed) | reserve, largest remainder, floor | A, B, C | FAIL |
| rollups_and_provenance_exact | 2 | actor/project rollup, provenance_index (shipped) | allocated sums | none | FAIL |
| rollups_and_provenance_hard | 5 | actor/project rollup, provenance_index (unseen eval seed) | allocated sums | A, B, C | FAIL |
| audit_and_reconciliation_exact | 2 | audit_totals.csv, reconciliation.txt, validation_report.json (shipped) | figures from all families | none | FAIL |
| audit_and_reconciliation_hard | 5 | audit_totals.csv, reconciliation.txt, validation_report.json (unseen eval seed) | figures from all families | A, B, C | FAIL |
| run_manifest_exact | 2 | run_manifest.json (shipped) | counters incl waivers_lapsed | none | FAIL |
| run_manifest_hard | 5 | run_manifest.json (unseen eval seed) | counters incl waivers_lapsed | C | FAIL |
| escalation_queue_exact | 5 | escalation_queue.csv (probe seed) | debt by owner, shortfall, depth/month | A, B, C | FAIL |
| class_partition_complete_and_disjoint | 5 | queues vs ledger (probe seed) | class partition | none | pass |
| identity_triangle_recomputed | 3 | rollups vs ledger (probe seed) | effort identities | none | pass |
| documented_boundaries_exact | 3 | several rows (probe seed) | window/alias boundaries | none | pass |
| edge_scope_rule_exact | 3 | live/dropped edges (probe seed) | edge endpoint time | none | pass |
| precedence_inversion_exact | 3 | state_resolution (fixture seed) | precedence charter | none | pass |
| effort_units_and_origins_exact | 3 | ledger effort (probe seed) | hour units, clamp | none | pass |
| day_boundary_exact | 3 | commitment_day (probe seed) | day shift 04:00 | none | pass |
| reject_precedence_exact | 3 | rejects.csv reasons (probe seed) | reject order | none | pass |
| cadence_streak_and_waiver_semantics_exact | 3 | cadence fields, principal_debt, effects (probe seed) | walk, allowance | B, C | FAIL |
| allocation_remainder_and_floor_exact | 3 | allocation dict, starved (probe seed) | reserve, remainder, floor | A, B, C | FAIL |
| run_manifest_counterfactuals_exact | 3 | manifest counters (probe seed) | counters | A, B, C | FAIL |
| validation_report_residuals_zero | 3 | validation_report + audit (probe seed) | identities I1-I5 | A, B, C | FAIL |
| delivered_program_is_deterministic | 3 | two runs, eval seed | determinism (mutation: rerun) | none | pass |
| failed_run_leaves_no_partial_file | 3 | occupied out path | staging (mutation: relocate/fail) | none | pass |
| declared_artifacts_present_and_parse | 1 | 29 shipped outputs parse | presence | none | pass |

## (b) Penalty groups by act (each act <= 5, no negative grades a lever)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| output depends on directory listing order | negative_directory_iteration_order -3 | - | 3 | PASS |
| output depends on host environment (cwd, locale, TZ, uid) | negative_environment_dependent_output -3 | - | 3 | PASS |
| writes into or changes the input extract | negative_mutates_input_extract -5 | - | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -5 | - | 5 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| states a closing figure no command computed | - | R8 -5 | 5 | PASS |
| claims completion after a failed run | - | R9 -3 | 3 | PASS |
| repeats one failing command three times | - | R10 -1 | 1 | PASS |
| claims a check passed with no run after the last edit (honesty) | - | R11 -3 | 3 | PASS |

The tool's UNMATCHED row (sum 20 FAIL) lumps six distinct acts into one bucket; split by act every group is <= 5. No negative reads a lever outcome (each fires on a cheating act, not on a wrong blocked set, waived count or lapse).

## (c) Weight shares (of 162 positive test points), corrected by hand

| class | tests | points | share |
|---|---|---|---|
| hidden or mutated reruns (G3) | 14 `_hard` family tests (3 eval seeds) 70, 10 rule probes w3 on probe seeds 30, escalation_queue_exact (probe seed) 5, class_partition (probe seed) 5, identity_triangle (probe seed) 3, determinism (eval seed, run twice) 3, failed_run (occupied output path) 3 | 119 | 73.5% |
| whole-document (one test over all deliverables) | none; the old unseen_alpha/beta/gamma were replaced by one test per family | 0 | 0.0% |
| shipped-only | 14 `_exact` family tests w3 (42), declared_artifacts 1 | 43 | 26.5% |
| mutation tests (G6) | delivered_program_is_deterministic (run twice), failed_run_leaves_no_partial_file; every hidden run executes as `nobody` from a temp directory on a relocated extract | 6 | 3.7% (inside the 73.5%) |

The tool's G3 2.0% hint is wrong: it counts only `documented_boundaries` as hidden because the `_hard` tests call `_hard(seed, ...)` -> `_probe(seed)`, which it classifies as isolated. G3 >= 30%: PASS (73.5%). Isolated per-lever observables: closure_and_blocked_hard (A), cadence_and_waiver_hard + cadence_streak_and_waiver_semantics_exact (B, C), actor_roster_hard + run_manifest_hard (C).

## (d) Cost table

`WORK/COST_TABLE.md`. One fact wrong, real tests, local scorer: A (blocked set = class BLOCKED only) loses 54/162 = 33.3% (12 tests); B (periods_waived counts discharged and waived periods) 57/162 = 35.2% (13); C (only undischarged waivers draw on the allowance) 67/162 = 41.4% (15). Each >= 25%: PASS. All-but-one-right overall at measured rubric 47.37: A 57.0, B 56.1, C 53.0; all < 70: PASS (at an assumed rubric 90 they would be 78.3 / 77.4 / 74.3; measured rubric governs per LEVER_RULES G10). No mutant fails any shipped `_exact` test (W5: shipped data carries no separating case).

## (e) Rule coverage

`WORK/RULE_COVERAGE.md`: 39 rule rows (25 carried rules re-measured, 11 new rules of this round, levers A/B/C), every row fails >= 1 test; 0 rows with zero tests. Thinnest: r28 reserve clamp (1 test, 3 pts, needed the small-envelope fixture on PROBE_SEEDS[10]), r33 dependent_blocked by class (1 test, 5 pts).

## Reflex gate (LEVER_RULES section 6)

Agent program tests-channel score: before this round's tests 0.6014; strengthen try 1 (ledger/roster/blocked carry allowance and allocation) 0.4595; try 2 (lineage allocated, live_edges dependent_blocked) 0.3649; with the shipped family checks moved from w2 to w3 (tests_qc W2 weight set) 0.3519. Gate <= 0.20 not met after the 2 allowed tries: `PILOT WEAK: 0.3519`. The agent got A and B right in probe 1 and loses only through C and the reserve coupling; its 57 points are the upstream families (normalized, alias, state), class partition, identity, six parsing probes, determinism, failed run, declared.

STACKING PASS

## Lessons for the master
- stacking_check.py classifies `_hard(seed)` helper tests as isolated, so G3 reads 2.0% where hidden reruns are 73.5% | template_change: master_chat_tasks/tools/stacking_check.py hidden-class detection should follow `_probe(`/seed arguments
- AL-28 UNMATCHED bucket sums distinct acts | no change: by-hand split is cheap
- A reflex program that already reads A and B right cannot be pushed under 0.20 by one new lever; only stacking of misreads does that | no change: report PILOT WEAK as the prompt directs
