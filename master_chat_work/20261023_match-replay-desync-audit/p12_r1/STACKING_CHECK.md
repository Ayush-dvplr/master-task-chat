# STACKING_CHECK: match-replay-desync-audit (P12 r1, after fixes)

Tool: `master_chat_tasks/tools/stacking_check.py` on the fixed BUNDLE (raw output in `stacking_check_tool.txt`, rc 0). Every row confirmed by reading `tests/test_output.py`. Variant columns are local scores of the fixed tests (WORK/trap/scores_after), negatives stayed silent on every variant.

## (a) Test map and variant results

| test | w | class | agent | adapted | perentry | norenew | opening | cancelled_draw | carry_eleven |
|---|---|---|---|---|---|---|---|---|---|
| format_program_delivered | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| record_derivation_matches | 1 | isolated | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| format_writes_only_named_reports | 1 | isolated | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| instance_scenario_visible | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| instance_perf_report | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| instance_recommendations | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| instance_data_quality | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| instance_report_serialization | 1 | shipped_only | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| general_scenario_peak | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_scenario_steady | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_scenario_latency | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_sealed_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_chained_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_stepped_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_drifted_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_woven_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_echoed_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_flipped_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_padded_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_shadowed_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_spun_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_aliased_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| trap_warded_inverse | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_deep_identity_chain | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_charter_cap_surplus | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_empty_charter | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_window_boundary_shift | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_degenerate_window_live | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_dead_window | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_reversal_density | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_population_scale | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_baseline_scale | 5 | whole_doc | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| general_reversal_tiebreak | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_cadence_partition | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_fixpoint_new_unit | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| general_donor_table_rotation | 5 | whole_doc | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| mutation_cadence_modulus_moves_only_classes | 5 | mutation | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| mutation_window_split_moves_only_amounts | 5 | mutation | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| negative_hardcoded_sample_answers | -5 | negative | silent | silent | silent | silent | silent | silent | silent |
| negative_filename_dependent_behaviour | -5 | negative | silent | silent | silent | silent | silent | silent | silent |
| negative_reads_supplied_answer_data_at_runtime | -5 | negative | silent | silent | silent | silent | silent | silent | silent |
| negative_rebinds_verifier_dependencies | -5 | negative | silent | silent | silent | silent | silent | silent | silent |

## (b) TS-26 duplicate candidates checked by hand

The six groups the tool lists share a report name and the `_compare` helper, but each test stages its own corpus (`_trap_only(tag)` turns on exactly one transform bit; `_mutant(tag)` applies one generator tweak; each with its own seed and, after P12, its own drawn eleven quantities). Different inputs, one whole document each, so no double payment (TS-26 holds). The new `format_writes_only_named_reports` reads the directory listing of the cadence-peak run, which no other test grades; `record_derivation_matches` reads the record of the deepchain run, which no other test grades (general_deep_identity_chain grades scenario_visible.json of the same run).

## (c) Penalty groups

AL-28: every act at most 5 (tool section 3). PASS.

## (d) Shares

whole-document 140/158 = 88.6% (>= 50%), isolated+mutation 12/158 = 7.6% (<= 30%), shipped-only 6/158 = 3.8% (<= 5%). Reflex: agent 18/158 = 0.114, adapted 0.114, every single-lever variant 0.114, carry-eleven-in-source 6/158 = 0.038 (all <= 0.20).

## Verdict

STACKING: PASS (caps: 42 tests is the known TS-23 warn, kept, see PL_NOTE.md).

## Lessons for the master

- The tool flags same-helper, different-corpus tests as TS-26 candidates; reading the staging tag settles them.
