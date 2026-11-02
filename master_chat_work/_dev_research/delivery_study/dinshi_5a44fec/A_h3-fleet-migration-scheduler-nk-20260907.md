# A — h3-fleet-migration-scheduler-nk-20260907

**Verdict: GENUINE** (one wrong definition reading; no crash, gate, path or permission artefact).

Recorded: overall 64.77 / tests 70.71 / rubric 58.82 (score.json). Positive test weight 99; lost 29 = 3+3+3+5+5+5+5 → 70/99 = 70.71 (matches).

## Artefact evidence (none found)
- result.json `exception_info: null`; agent ran 12:15:19-12:28:46 UTC (13.5 min of 21600 s budget).
- report.json: 22 pass / 13 fail; the 6 negatives all `passed:false` = not fired (arithmetic above confirms).
- verifier/ctrf.json failure messages empty; test-stdout.txt only `reward:`.
- All 11 files present in artifacts/app/out (final_state, fixed_point_trace, fleet_utilization, integrity_manifest, migration_ledger, objective_breakdown, preemption_events, reusable_scheduler.py, schedule_matrix, sla_violation_report, tenant_fairness_report).
- Program ran on every fixture: all 9 fresh-fixture rule tests (test_output.py:619-816) and the 5 sealed-witness tests (884-913) PASSED — these invoke the agent program on new data.

## Failed checks — wrong VALUE, all traced to one definition
Decoded the embedded golden results (`_GOLDEN_RESULTS_B64`, test_output.py:417, decoded by `_golden_results` :482; fingerprint of shipped environment/data matched a key). Shipped-run comparison, agent vs golden:
- schedule_matrix, fleet_utilization, migration_ledger, preemption_events, sla_violation_report: **EQUAL**.
- objective_breakdown: want `fairness_deviation 26, total_cost 1431`; got `12, 1403` (all other terms equal).
- fixed_point_trace: want admitted_total 18,18,18,18,13,13,12,12; got 18,18,19,19,19,19,19,19.
- tenant_fairness_report: e.g. T03 epoch 2 want admitted 2 / deviation 2; got 3 / 1.

Cause: the oracle counts `admitted` = streams **placed** (solve.py:516-518 counts `assignments`; :578-582 same for the report). The agent counted streams **selected in phase 5** (placed + preempted): agent epoch 1 has 18 assignments + 1 preempted (S022) = 19.
Wording: README-input-schema.md:58 "Sort admitted streams globally by:" (phase 6, before placement) and :79 "When an unplaced admitted stream `s`…" use *admitted* for pre-placement selected streams; :90 `fairness_deviation[e] = sum over t of |admitted_count[t, e] - target[t, e]|` never defines admitted_count. Shipped data cannot separate the readings: worked_micro_example.json has no preemption ("phase_6b_cascade": "none"); seals with cost (argosy/brigantine/caravel) all have `preempted_count 0`; dhow/esquif/frigate seals have no cost/count.

| failed test | w | what is compared | cause |
|---|---|---|---|
| shipped_fixed_point_trace_converges_within_tolerance | 3 | whole trace (test_output.py:725) | admitted_total — observed |
| shipped_tenant_report_has_every_epoch | 3 | whole report (:736) | admitted/deviation — observed |
| shipped_final_state_matches_reviewed_result | 3 | stream_count, epoch_count, total_cost (:866) | total_cost 1403 vs 1431 — observed |
| hidden_tight_slo_fairness | 5 | one scalar: tenant[0] epoch[0] deviation (:840ff) | INFERRED same definition (cannot run agent on seeded corpus) |
| hidden_burst_arrival_fixed_point | 5 | iterations[4].admitted_total | INFERRED same |
| hidden_migration_dominant_objective | 5 | total_cost | INFERRED same |
| hidden_oversubscribed_objective | 5 | fairness_deviation | INFERRED same |

Not a gate: other files of the same runs are exact; one value rule feeds four output fields reused by 7 tests (natural cascade, TS-26 style).
Is the rule clearly stated? **No** — the term is overloaded in the spec and the counted set is never named (candidate HIDDEN RULE / "implied by a definition"; Step 2 to confirm against the agent's own reading).
