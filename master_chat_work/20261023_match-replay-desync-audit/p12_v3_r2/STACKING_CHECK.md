# STACKING_CHECK (0bf6688, match-replay-desync-audit, P12 v3 r2)

Tool: `master_chat_tasks/tools/stacking_check.py` (exit 0). Raw output in the last section. Verdict: **PASS** after hand corrections.

## Hand corrections (tool hints are static)
- `record_derivation_matches` (w3) and `format_writes_only_named_reports` (w1) are classed "isolated" by default; both run the program on fresh held-out corpora (`_mutant`, `_held_out`), so they are hidden reruns. G3 hidden or mutated share is therefore 97.5% (140 + 10 + 4 of 160), not 93.8%; PASS either way.
- TS-26 "duplicate candidates": false. Each check stages its own input: `_trap_only("<transform>", BIT_<TRANSFORM>)` per trap test (test_output.py:2396-2460), `_mutant("<tweak>")` per general test (e.g. `cap` :2463, `deadwindow` :2483). Same helper, different observable input; QC v2 passed TS-26.
- J1 hint on R11: the figure is the 150-line threshold of the J4 template, not a what-if figure the oracle must print. No issue.
- J2 conduct criteria R7, R8, R9 found correctly this time (no "none" bug). R11 is conduct-labelled code quality (JD-15, "agent behavior").
- AL-28 penalty groups all <= 5: PASS. Weights only 1, 3, 5 and -3, -5.

## Raw tool output
# stacking_check: match-replay-desync-audit

tests/test_output.py: 42 checks, positive total 160, negatives -20; judge: 11 criteria, positive 17, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| format_program_delivered | 1 | shipped_only (artifact/shipped wording) | the delivered settlement program exists and parses. | _passes, test_format_program_delivered | 0/0 |
| record_derivation_matches | 3 | isolated (default (rule/fixture/case check)) | bottleneck_analysis.json | _mutant, record_derivation_ok, _produced | 0/0 |
| format_writes_only_named_reports | 1 | isolated (default (rule/fixture/case check)) | cadence-peak, code, the delivered program exited %d: %s, result ... | _held_out | 0/0 |
| instance_scenario_visible | 1 | shipped_only (artifact/shipped wording) | the shipped scenario report matches the shipped capture set. | _passes, test_instance_scenario_visible | 0/0 |
| instance_perf_report | 1 | shipped_only (artifact/shipped wording) | perf_report.json | _match_shipped | 0/0 |
| instance_recommendations | 1 | shipped_only (artifact/shipped wording) | the shipped bench report matches the shipped capture set. | _passes, test_instance_recommendations | 0/0 |
| instance_data_quality | 1 | shipped_only (artifact/shipped wording) | the shipped quality report matches the shipped capture set. | _passes, test_instance_data_quality | 0/0 |
| instance_report_serialization | 1 | shipped_only (format check, no hidden-input wording) | %s is not a report object, %s does not follow the example report's serialization | _shipped_text | 0/0 |
| general_scenario_peak | 5 | whole_doc (whole-document wording) | scenario_peak.json | _compare, _held_out | 0/0 |
| general_scenario_steady | 5 | whole_doc (whole-document wording) | scenario_steady.json | _compare, _held_out | 0/0 |
| general_scenario_latency | 5 | whole_doc (whole-document wording) | scenario_latency.json | _compare, _held_out | 0/0 |
| trap_sealed_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_chained_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_stepped_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_drifted_inverse | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _trap_only | 0/0 |
| trap_woven_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_echoed_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_flipped_inverse | 5 | whole_doc (whole-document wording) | data_quality.json | _compare, _trap_only | 0/0 |
| trap_padded_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_shadowed_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_spun_inverse | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _trap_only | 0/0 |
| trap_aliased_inverse | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _trap_only | 0/0 |
| trap_warded_inverse | 5 | whole_doc (whole-document wording) | data_quality.json | _compare, _trap_only | 0/0 |
| general_deep_identity_chain | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _mutant | 0/0 |
| general_charter_cap_surplus | 5 | whole_doc (whole-document wording) | data_quality.json | _compare, _mutant | 0/0 |
| general_empty_charter | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _mutant | 0/0 |
| general_window_boundary_shift | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _mutant | 0/0 |
| general_degenerate_window_live | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _mutant | 0/0 |
| general_dead_window | 5 | whole_doc (whole-document wording) | data_quality.json | _compare, _mutant | 0/0 |
| general_reversal_density | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _mutant | 0/0 |
| general_population_scale | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _mutant | 0/0 |
| general_baseline_scale | 5 | whole_doc (whole-document wording) | recommendations.json | _compare, _mutant | 0/0 |
| general_reversal_tiebreak | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _mutant | 0/0 |
| general_cadence_partition | 5 | whole_doc (whole-document wording) | scenario_burst.json | _compare, _mutant | 0/0 |
| general_fixpoint_new_unit | 5 | whole_doc (whole-document wording) | perf_report.json | _compare, _mutant | 0/0 |
| general_donor_table_rotation | 5 | whole_doc (whole-document wording) | scenario_visible.json | _compare, _mutant | 0/0 |
| mutation_cadence_modulus_moves_only_classes | 5 | mutation (mutation in name or description lead) | scenario_visible.json | _mutation_pair, _settled_view, _cadence_marks | 0/0 |
| mutation_window_split_moves_only_amounts | 5 | mutation (mutation in name or description lead) | perf_report.json, scenario_visible.json | _mutation_pair, _compare, _cadence_marks | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | fires when settled figures are baked in as literals. | _passes, test_negative_weight_hardcoded_sample_answers | 0/0 |
| negative_filename_dependent_behaviour | -5 | negative (weight < 0 or negative_ name) | fires when output depends on the staged directory name. | _passes, test_negative_weight_filename_dependent_behaviour | 0/0 |
| negative_reads_supplied_answer_data_at_runtime | -5 | negative (weight < 0 or negative_ name) | /out/, scenario_visible.json, perf_report.json, data_quality.json | _executable_source | 0/0 |
| negative_rebinds_verifier_dependencies | -5 | negative (weight < 0 or negative_ name) | fires when the program reaches into the grading machinery. | _passes, test_negative_weight_rebinds_verifier_dependencies | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): trap_sealed_inverse = trap_chained_inverse = trap_stepped_inverse = trap_woven_inverse = trap_echoed_inverse = trap_padded_inverse = trap_shadowed_inverse = trap_aliased_inverse; trap_drifted_inverse = trap_spun_inverse; trap_flipped_inverse = trap_warded_inverse; general_deep_identity_chain = general_window_boundary_shift = general_degenerate_window_live = general_population_scale = general_donor_table_rotation; general_charter_cap_surplus = general_dead_window; general_empty_charter = general_reversal_density = general_reversal_tiebreak = general_fixpoint_new_unit

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -5 | - | 5 | PASS |
| reads data beyond its argument | negative_reads_supplied_answer_data_at_runtime -5 | - | 5 | PASS |
| rebinds verifier dependencies | negative_rebinds_verifier_dependencies -5 | - | 5 | PASS |
| edits outside its scope | - | R6 -3 | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R10 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 140 (87.5%)
- format_hidden: 0 (0.0%)
- isolated: 4 (2.5%)
- mutation: 10 (6.2%)
- shipped_only: 6 (3.8%)
- G3: hidden or mutated reruns 93.8% (>= 30%); isolated+mutation 8.8%, whole-document 87.5%, shipped-only 3.8% (info, no cap)

## 5. Caps and weights

- tests 42, criteria 11 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): format_program_delivered, format_writes_only_named_reports, instance_scenario_visible, instance_perf_report, instance_recommendations, instance_data_quality, instance_report_serialization
- judge J1 hints (criterion quotes a figure): R11
- judge J2 conduct criteria: R7, R8, R9

## Verdict hints

- TS-26 duplicate candidates: 6 group(s): CHECK BY HAND
- AL-28 groups <= 5: PASS
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 93.8% PASS
- G3 isolated / shipped-only (info, no cap): 8.8% / 3.8%
- tests >= 10 (no cap): 42 PASS
- criteria >= 8 (no cap): 11 PASS
- judge mode batched: batched
