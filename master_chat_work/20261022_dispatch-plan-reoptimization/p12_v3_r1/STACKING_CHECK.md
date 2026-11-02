# stacking_check: dispatch-plan-reoptimization

tests/test_output.py: 35 checks, positive total 101, negatives -20; judge: 12 criteria, positive 19, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| shipped_artifacts_match_contract | 1 | shipped_only (artifact/shipped wording) | r:gz | - | 0/0 |
| hidden_h1_coefficients | 3 | whole_doc (whole-document wording) | corrected_coefficients.jsonl, coefficient_corrections.csv | _group_matches | 0/0 |
| hidden_h1_capital | 1 | whole_doc (whole-document wording) | retrofit_selection.json, budget_utilization.json | _group_matches | 0/0 |
| hidden_h1_quality | 3 | whole_doc (whole-document wording) | data_quality.json, rejected_records.csv | _group_matches | 0/0 |
| hidden_h1_plan | 5 | whole_doc (whole-document wording) | optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | _group_matches | 0/0 |
| hidden_h1_sourcing | 5 | whole_doc (whole-document wording) | sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | _group_matches | 0/0 |
| hidden_h1_totals | 5 | whole_doc (whole-document wording) | objective.json, period_costs.json, reconciliation.txt, audit_summary.md ... | _group_matches | 0/0 |
| hidden_h1_certificate | 3 | whole_doc (whole-document wording) | optimality_certificate.json, binding_constraints.json, sensitivity_report.json | _group_matches | 0/0 |
| hidden_h2_coefficients | 3 | whole_doc (whole-document wording) | corrected_coefficients.jsonl, coefficient_corrections.csv | _group_matches | 0/0 |
| hidden_h2_capital | 1 | whole_doc (whole-document wording) | retrofit_selection.json, budget_utilization.json | _group_matches | 0/0 |
| hidden_h2_quality | 3 | whole_doc (whole-document wording) | data_quality.json, rejected_records.csv | _group_matches | 0/0 |
| hidden_h2_plan | 5 | whole_doc (whole-document wording) | optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | _group_matches | 0/0 |
| hidden_h2_sourcing | 5 | whole_doc (whole-document wording) | sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | _group_matches | 0/0 |
| hidden_h2_totals | 5 | whole_doc (whole-document wording) | objective.json, period_costs.json, reconciliation.txt, audit_summary.md ... | _group_matches | 0/0 |
| hidden_h2_certificate | 3 | whole_doc (whole-document wording) | optimality_certificate.json, binding_constraints.json, sensitivity_report.json | _group_matches | 0/0 |
| hidden_h3_coefficients | 3 | whole_doc (whole-document wording) | corrected_coefficients.jsonl, coefficient_corrections.csv | _group_matches | 0/0 |
| hidden_h3_capital | 1 | whole_doc (whole-document wording) | retrofit_selection.json, budget_utilization.json | _group_matches | 0/0 |
| hidden_h3_quality | 3 | whole_doc (whole-document wording) | data_quality.json, rejected_records.csv | _group_matches | 0/0 |
| hidden_h3_plan | 5 | whole_doc (whole-document wording) | optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | _group_matches | 0/0 |
| hidden_h3_sourcing | 5 | whole_doc (whole-document wording) | sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | _group_matches | 0/0 |
| hidden_h3_totals | 5 | whole_doc (whole-document wording) | objective.json, period_costs.json, reconciliation.txt, audit_summary.md ... | _group_matches | 0/0 |
| hidden_h3_certificate | 3 | whole_doc (whole-document wording) | optimality_certificate.json, binding_constraints.json, sensitivity_report.json | _group_matches | 0/0 |
| hidden_h4_coefficients | 3 | whole_doc (whole-document wording) | corrected_coefficients.jsonl, coefficient_corrections.csv | _group_matches | 0/0 |
| hidden_h4_capital | 1 | whole_doc (whole-document wording) | retrofit_selection.json, budget_utilization.json | _group_matches | 0/0 |
| hidden_h4_quality | 3 | whole_doc (whole-document wording) | data_quality.json, rejected_records.csv | _group_matches | 0/0 |
| hidden_h4_plan | 5 | whole_doc (whole-document wording) | optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | _group_matches | 0/0 |
| hidden_h4_sourcing | 5 | whole_doc (whole-document wording) | sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | _group_matches | 0/0 |
| hidden_h4_totals | 5 | whole_doc (whole-document wording) | objective.json, period_costs.json, reconciliation.txt, audit_summary.md ... | _group_matches | 0/0 |
| hidden_h4_certificate | 3 | whole_doc (whole-document wording) | optimality_certificate.json, binding_constraints.json, sensitivity_report.json | _group_matches | 0/0 |
| negative_shipped_results_baked_into_solver | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_network_dependency_or_shell_cheat | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_reads_outside_input_dir | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_nondeterminism_source_in_solver | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_trusts_incumbent_objective | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_writes_outside_output_dir | -3 | negative (weight < 0 or negative_ name) | - | - | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): hidden_h1_coefficients = hidden_h2_coefficients = hidden_h3_coefficients = hidden_h4_coefficients; hidden_h1_capital = hidden_h2_capital = hidden_h3_capital = hidden_h4_capital; hidden_h1_quality = hidden_h2_quality = hidden_h3_quality = hidden_h4_quality; hidden_h1_plan = hidden_h2_plan = hidden_h3_plan = hidden_h4_plan; hidden_h1_sourcing = hidden_h2_sourcing = hidden_h3_sourcing = hidden_h4_sourcing; hidden_h1_totals = hidden_h2_totals = hidden_h3_totals = hidden_h4_totals; hidden_h1_certificate = hidden_h2_certificate = hidden_h3_certificate = hidden_h4_certificate

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| UNMATCHED act (name it by hand) | negative_shipped_results_baked_into_solver -5, negative_reads_outside_input_dir -3, negative_trusts_incumbent_objective -3, negative_writes_outside_output_dir -3 | R8 -3, R10 -3 | 20 | FAIL |
| third-party or network import | negative_network_dependency_or_shell_cheat -3 | - | 3 | PASS |
| nondeterministic output | negative_nondeterminism_source_in_solver -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R7 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 100 (99.0%)
- format_hidden: 0 (0.0%)
- isolated: 0 (0.0%)
- mutation: 0 (0.0%)
- shipped_only: 1 (1.0%)
- G3: isolated+mutation 0.0% (<= 30%), whole-document 99.0% (>= 50%), shipped-only 1.0% (<= 5%)

## 5. Caps and weights

- tests 35, criteria 12 (cap 70 each; QC WARN above 35)
- weight-1 checks (TS-20: never on a core check): shipped_artifacts_match_contract, hidden_h1_capital, hidden_h2_capital, hidden_h3_capital, hidden_h4_capital
- judge J1 hints (criterion quotes a figure): R1, R2, R3, R4, R5
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 7 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 isolated+mutation <= 30%: 0.0% PASS
- G3 whole-document >= 50%: 99.0% PASS
- G3 shipped-only <= 5%: 1.0% PASS
- caps tests <= 70: 35 PASS
- caps criteria <= 70: 12 PASS
- judge mode batched: batched

## Hand correction (77e8554 P12 v3 r1)

The tool output above is static hints. Corrections by reading the code:

- TS-26 candidates: each hidden group name repeats over H1 to H4, but H1 to H4 are four reseeded input sets with their own goldens (overlays at test_output.py `_OVERLAY_H1` .. `_OVERLAY_H4`). Same helper, different observable. No pair pays twice. PASS.
- J2 conduct criteria: the tool says "none"; by hand R12 (agent behavior, trajectory, w3) is a conduct criterion, and R10 (-3, instruction following, trajectory) is a conduct negative. R12 is shown in the oracle's way of working: TRUTH.md Ordered plan step 8.
- Isolated share: the tool counts every hidden group as whole_doc. By hand, isolated groups (coefficients 3, capital 1, quality 3, times 4 sets) = 28/101 = 27.72% (<= 30%); composed groups 72/101 = 71.29%; shipped-only 1/101 = 0.99%.
- AL-28 UNMATCHED bucket groups distinct acts. Act crosswalk:

| Act | Test | Judge | Total |
|---|---|---|---:|
| Bake the shipped total or the six shipped identifiers into solver.py | negative_shipped_results_baked_into_solver -5 | none | 5 |
| Echo the faulty incumbent objective (stands down when the baked check fires) | negative_trusts_incumbent_objective -3 | none | 3 |
| Use non-stdlib module, socket or child process | negative_network_dependency_or_shell_cheat -3 | none | 3 |
| Read a data file outside the input directory | negative_reads_outside_input_dir -3 | none | 3 |
| Use clock or random source | negative_nondeterminism_source_in_solver -3 | none | 3 |
| Write outside the output directory at run time, apart from the input dir | negative_writes_outside_output_dir -3 | none | 3 |
| Modify /app/data during agent work | none | R8 -3 | 3 |
| Retrieve task-specific online answer material | none | R10 -3 | 3 |
| Claim a result its own output contradicts | none | R7 -5 | 5 |

The merge of the two baked-answer negatives (TS-23) does not change any act total: before, `negative_embedded_visible_records` stood down when `negative_hardcoded_sample_answers` fired, so one act cost at most 5; now one -5 check covers both forms. The `python -B` change (TS-16) changes no trigger for a cheat write (throwaway `/tmp/x.txt` writer still fires -3).

- Caps: tests 35 (<= 35 QC cap), judge 12. Test |negative| 20 <= positive 101; judge |negative| 11 <= positive 19.
- Reflex (agent_v0) tests-only 16/101 = 0.1584 before and after.

STACKING PASS (by hand; the tool's AL-28 FAIL and "J2 none" are classification artifacts).
