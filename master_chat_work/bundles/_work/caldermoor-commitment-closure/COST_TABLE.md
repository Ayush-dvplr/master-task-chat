# COST_TABLE caldermoor-commitment-closure (harden r2, 593ecae; fix r2 5f2e150)

## Fix round 2 (5f2e150), P = 186

Same method, run in the verifier image (WORK/fz/score.py, mkmut.py, score_chain.sh;
results WORK/fz/score_before.jsonl at P = 162 and score_after1.jsonl at P = 186).
The six survivor tests (+24) were added; no existing test changed.

| lever | one fact wrong (mutant) | kept before (P 162) | kept after (P 186) | points lost after | share |
|---|---|---|---|---|---|
| A blocked predicate | as below | 108 (66.67%) | 108 (58.06%) | 78 | 41.9% |
| B first-match walk | as below | 105 (64.81%) | 105 (56.45%) | 81 | 43.5% |
| C waiver allowance | as below | 95 (58.64%) | 95 (51.08%) | 91 | 48.9% |
| H7 survivor re-entry (new) | the second share re-enters the at-or-below branch: survivors whose clamped effort fits the distributable minutes get only that effort, the rest left undistributed | 162 (100.00%) | 162 (87.10%) | 24 | 12.9% |

A, B and C each also fail all six survivor tests through the reserve (COUPLING).
H7 alone is 12.9%, below the G10 25% line, by design of this round: the
master's target is the probe-2 agent program (which makes exactly the H7 slip)
at about 85% to 95% of tests; it scores 162/186 = 87.10%, failing exactly the
six survivor tests. H7 stays one fact wrong: only `allocated_minutes` of the
survivor principal-months and its carriers move.

| only this lever wrong | tests | overall at judge 4.55 | overall at rubric 90 |
|---|---|---|---|
| A | 58.06 | 31.3 | 74.0 |
| B | 56.45 | 30.5 | 73.2 |
| C | 51.08 | 27.8 | 70.5 |
| H7 (probe-2 agent program) | 87.10 | 45.8 | 88.5 |

At the measured judge 1/22 = 4.55 every row is under 70. At rubric 90 only H7
is over 70 (88.5); its cost is capped by the 85% to 95% target.

## Harden round 2 (593ecae), P = 162


Method (G10): each wrong reading is injected into a copy of `solution/solve.py`
(patch script `mkmut.py` in the session temp dir, never the bundle), the copy
is run as the delivered program on a copy of the shipped extract, and every
registered check of the real `tests/test_output.py` is run against it with
rewardkit stubbed (local scorer `score.py`; oracle 1.0000, nop 0.0000). Hidden
and probe checks rerun the mutant program on their own seeds exactly as the
verifier does. Total positive test points: 162 (49 tests, 44 positive; shipped family checks at w3 after tests_qc W2).

| lever | one fact wrong (mutant) | points lost | share | tests failed |
|---|---|---|---|---|
| A blocked predicate | closure roots skip SETTLED, WITHDRAWN and ambiguous-obligee dependents (blocked set = class BLOCKED) | 54 | 33.3% | allocation_and_load_hard 5, allocation_remainder_and_floor_exact 3, audit_and_reconciliation_hard 5, closure_and_blocked_hard 5, commitment_ledger_hard 5, edge_partition_hard 5, escalation_queue_exact 5, project_lineage_hard 5, queues_and_registers_hard 5, rollups_and_provenance_hard 5, run_manifest_counterfactuals_exact 3, validation_report_residuals_zero 3 |
| B first-match walk | a period both discharged and waived is also counted in periods_waived | 57 | 35.2% | allocation_and_load_hard 5, allocation_remainder_and_floor_exact 3, audit_and_reconciliation_hard 5, cadence_and_waiver_hard 5, cadence_streak_and_waiver_semantics_exact 3, closure_and_blocked_hard 5, commitment_ledger_hard 5, escalation_queue_exact 5, project_lineage_hard 5, queues_and_registers_hard 5, rollups_and_provenance_hard 5, run_manifest_counterfactuals_exact 3, validation_report_residuals_zero 3 |
| C waiver allowance (new) | only waivers in undischarged periods draw on the allowance | 67 | 41.4% | actor_roster_hard 5, allocation_and_load_hard 5, allocation_remainder_and_floor_exact 3, audit_and_reconciliation_hard 5, cadence_and_waiver_hard 5, cadence_streak_and_waiver_semantics_exact 3, closure_and_blocked_hard 5, commitment_ledger_hard 5, escalation_queue_exact 5, project_lineage_hard 5, queues_and_registers_hard 5, rollups_and_provenance_hard 5, run_manifest_counterfactuals_exact 3, run_manifest_hard 5, validation_report_residuals_zero 3 |

Every lever alone costs at least 25% of test points (G10 met). No mutant fails
a shipped family check (`*_exact` w3): the shipped extract carries no row that
separates any of the three readings (W5), so each loss is on hidden or probe
extracts only. Each mutant stays one fact wrong (CL-4): the spread past the
lever's own family comes only through the stated COUPLING quantity, the
envelope reserve (commitment-protocol.md section 9), which every
`allocated_minutes` carrier reads, plus the stated carriers
(`dependent_blocked`, `waivers_granted`/`waivers_lapsed`).

## All but one right (overall)

Measured rubric of probe 1: 47.37. Overall = (tests + rubric) / 2.

| only this lever wrong | tests | overall at rubric 47.37 | overall at rubric 90 |
|---|---|---|---|
| A | 66.7 | 57.0 | 78.3 |
| B | 64.8 | 56.1 | 77.4 |
| C | 58.6 | 53.0 | 74.3 |

At the measured rubric every row is under 70. At the default rubric 90 no row
is under 70; the measured rubric governs (LEVER_RULES G10).

## Reflex program

The probe-1 agent's final program (OUT/harden_r2/agent_program/reconcile.py),
which reads A and B correctly, scores 57/162 = 0.3519 on the tests channel; it
misses C, the reserve and the new carrier columns.

## Harden round 3 (da61544), P = 194 (57 tests, 52 positive)
Measured with WORK/fz/score.py on the real tests (rewardkit stub, shipped extract), mutants from WORK/fz/mkmut.py on the r3 solve.py (OUT/proto/m4) plus OUT/proto/mut_N2.

| lever | one fact wrong (mutant) | kept | points lost | share | 25% gate |
|---|---|---|---|---|---|
| N2 wait (new) | chain_depth in place of wait in the reserve | 126 | 68 | 35.05% | PASS (25-45% band) |
| A blocked set | blocked set = class BLOCKED | 106 | 88 | 45.36% | PASS |
| B waived periods | discharged and waived counted as waived | 100 | 94 | 48.45% | PASS |
| C allowance (H6) | only suppressing waivers draw | 95 | 99 | 51.03% | PASS |
| H7 second share | second pass re-enters the fits branch | 170 | 24 | 12.37% | below 25% (kept as is; master: never weaken H7) |

N2 fails 16 checks: allocation_and_load_hard 5, allocation_remainder_and_floor_exact 3, audit_and_reconciliation_hard 5, closure_and_blocked_hard 5, commitment_ledger_hard 5, escalation_queue_exact 5, project_lineage_hard 5, queues_and_registers_hard 5, rollups_and_provenance_hard 5, run_manifest_hard 5, survivor_allocation_exact 3, survivor_ledger_exact 3, survivor_month_load_exact 3, validation_report_residuals_zero 3, wait_reserve_exact 3, wait_reserve_hard 5.

| only this lever wrong | tests | overall at rubric 13.64 (probe 3) | overall at rubric 90 |
|---|---|---|---|
| N2 | 64.95 | 39.3 | 77.5 |
| A | 54.64 | 34.1 | 72.3 |
| B | 51.55 | 32.6 | 70.8 |
| C | 48.97 | 31.3 | 69.5 |
| H7 | 87.63 | 50.6 | 88.8 |

At the measured probe rubrics (13.64, 47.37) every row stays overall < 70; at an assumed rubric of 90 only C does. Probe-3 and probe-2 programs: 87/194 = 0.4485 each (they predate the wait rule and charge 30 per blocked line).
Fuzz (OUT/fz/fz_n2_300.jsonl, 300 corpora): oracle 0/300 differ, N2 mutant 299/300 (99.7%), probe-3 program 300/300 (100%).
