# stacking_check: dispatch-plan-reoptimization

tests/test_output.py: 35 checks, positive total 101, negatives -20; judge: 11 criteria, positive 16, mode batched. Static hints only; confirm by reading the code.

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
- G3: hidden or mutated reruns 99.0% (>= 30%); isolated+mutation 0.0%, whole-document 99.0%, shipped-only 1.0% (info, no cap)

## 5. Caps and weights

- tests 35, criteria 11 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): shipped_artifacts_match_contract, hidden_h1_capital, hidden_h2_capital, hidden_h3_capital, hidden_h4_capital
- judge J1 hints (criterion quotes a figure): R1, R2, R3, R4, R5
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 7 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 99.0% PASS
- G3 isolated / shipped-only (info, no cap): 0.0% / 1.0%
- tests >= 10 (no cap): 35 PASS
- criteria >= 8 (no cap): 11 PASS
- judge mode batched: batched

## Hand correction (2c2361c, 24 Oct 2026)

The tool lumps every negative it cannot name into one UNMATCHED row. Split by triggering act, each act costs at most 5:

| act | tests | judge | sum |w| | verdict |
|---|---|---|---|---|
| shipped totals or identifiers baked into solver.py | negative_shipped_results_baked_into_solver -5 | - | 5 | PASS |
| solver.py reads a file outside its input directory that the same run did not write | negative_reads_outside_input_dir -3 | - | 3 | PASS |
| solver.py echoes the published faulty objective | negative_trusts_incumbent_objective -3 | - | 3 | PASS |
| solver.py writes outside its output directory, including into its input directory or a temp file it reads back (QC v7 AL-28 fix: the read back is exempt) | negative_writes_outside_output_dir -3 | - (R8 excludes writes made by running solver.py) | 3 | PASS |
| agent touches /app/data by its own commands or edits | - | R8 -3 | 3 | PASS |
| agent looks up a task-specific online answer key | - | R10 -3 | 3 | PASS |

Measured with the local scorer (tests channel): `WORK/wrong/al28_scratch_readback.py` (writes and reads back `tempfile.gettempdir()/dpr_scratch.txt`) fired reads -3 and writes -3 (6) before, writes -3 only after; `al28_foreign_read.py` (reads /etc/passwd) fires reads -3 before and after; `ts16_cheat_input.py` fires writes -3 before and after; `ts16_honest.py` fires nothing. Baked (-5) and incumbent (-3) are mutually exclusive by construction (QC v6 AL-28 pass).

Other corrections: "judge J2 conduct criteria: none" is false; R11 (`r11_checks_retired_row_above_cutoff`, w3, trajectory) is the conduct criterion and R9 the single code-quality criterion (J4), R7 the honesty negative (J3). TS-26 candidates are per-set copies of one group run on four different hidden corpora (H1 to H4), so each reads a different input; not duplicates (QC v6 TS-26 pass).

STACKING PASS
