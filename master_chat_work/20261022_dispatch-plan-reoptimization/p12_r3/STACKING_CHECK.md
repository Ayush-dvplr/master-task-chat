# Stacking check, dispatch-plan-reoptimization P12 r3

`stacking_check.py` ran at 36 tests, positive 101, negatives -25; judge 10, positive 21, negatives -11. Its TS-26 candidates are the same artifact names under different H1-H4 inputs; the corpora and goldens differ. Its UNMATCHED AL-28 bucket groups distinct acts by unknown labels; the act crosswalk below resolves it.

## Test map

| ID | w | Observable | Decisive logic | Wrong-reading lever(s) that fail | Reflex |
|---|---:|---|---|---|---|
| all_artifacts_exist | 1 | 21 shipped artifact values and stated format | shipped gold vs output | none | fail |
| hidden_h1_coefficients | 3 | H1 corrected_coefficients.jsonl, coefficient_corrections.csv | type-sensitive value plus stated format | LV-DPR-02, LV-DPR-03 | fail |
| hidden_h1_capital | 1 | H1 retrofit_selection.json, budget_utilization.json | type-sensitive value plus stated format | none | pass |
| hidden_h1_quality | 3 | H1 data_quality.json, rejected_records.csv | type-sensitive value plus stated format | LV-DPR-04 | pass |
| hidden_h1_plan | 5 | H1 optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h1_sourcing | 5 | H1 sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | type-sensitive value plus stated format | LV-DPR-01 | fail |
| hidden_h1_totals | 5 | H1 objective.json, period_costs.json, reconciliation.txt, audit_summary.md, incumbent_delta.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03, LV-DPR-04 | fail |
| hidden_h1_certificate | 3 | H1 optimality_certificate.json, binding_constraints.json, sensitivity_report.json | type-sensitive value plus stated format | LV-DPR-02, LV-DPR-03 | fail |
| hidden_h2_coefficients | 3 | H2 corrected_coefficients.jsonl, coefficient_corrections.csv | type-sensitive value plus stated format | LV-DPR-02, LV-DPR-03 | fail |
| hidden_h2_capital | 1 | H2 retrofit_selection.json, budget_utilization.json | type-sensitive value plus stated format | none | pass |
| hidden_h2_quality | 3 | H2 data_quality.json, rejected_records.csv | type-sensitive value plus stated format | LV-DPR-04 | pass |
| hidden_h2_plan | 5 | H2 optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h2_sourcing | 5 | H2 sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | type-sensitive value plus stated format | LV-DPR-01 | fail |
| hidden_h2_totals | 5 | H2 objective.json, period_costs.json, reconciliation.txt, audit_summary.md, incumbent_delta.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03, LV-DPR-04 | fail |
| hidden_h2_certificate | 3 | H2 optimality_certificate.json, binding_constraints.json, sensitivity_report.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h3_coefficients | 3 | H3 corrected_coefficients.jsonl, coefficient_corrections.csv | type-sensitive value plus stated format | LV-DPR-02, LV-DPR-03 | fail |
| hidden_h3_capital | 1 | H3 retrofit_selection.json, budget_utilization.json | type-sensitive value plus stated format | none | pass |
| hidden_h3_quality | 3 | H3 data_quality.json, rejected_records.csv | type-sensitive value plus stated format | LV-DPR-04 | pass |
| hidden_h3_plan | 5 | H3 optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h3_sourcing | 5 | H3 sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-03 | fail |
| hidden_h3_totals | 5 | H3 objective.json, period_costs.json, reconciliation.txt, audit_summary.md, incumbent_delta.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03, LV-DPR-04 | fail |
| hidden_h3_certificate | 3 | H3 optimality_certificate.json, binding_constraints.json, sensitivity_report.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h4_coefficients | 3 | H4 corrected_coefficients.jsonl, coefficient_corrections.csv | type-sensitive value plus stated format | LV-DPR-02, LV-DPR-03 | fail |
| hidden_h4_capital | 1 | H4 retrofit_selection.json, budget_utilization.json | type-sensitive value plus stated format | none | pass |
| hidden_h4_quality | 3 | H4 data_quality.json, rejected_records.csv | type-sensitive value plus stated format | LV-DPR-04 | pass |
| hidden_h4_plan | 5 | H4 optimal_plan.jsonl, production_schedule.csv, holding_profile.csv, item_summary.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| hidden_h4_sourcing | 5 | H4 sourcing_allocation.csv, plant_utilization.csv, shortfall_ledger.csv | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02 | fail |
| hidden_h4_totals | 5 | H4 objective.json, period_costs.json, reconciliation.txt, audit_summary.md, incumbent_delta.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03, LV-DPR-04 | fail |
| hidden_h4_certificate | 3 | H4 optimality_certificate.json, binding_constraints.json, sensitivity_report.json | type-sensitive value plus stated format | LV-DPR-01, LV-DPR-02, LV-DPR-03 | fail |
| negative_hardcoded_sample_answers | -5 | numeric shipped-total literal in executable code | AST exact constant | none (cheat negative) | pass |
| negative_embedded_visible_records | -5 | six shipped identifiers used in executable code without baked total | AST exact constants | none (cheat negative) | pass |
| negative_network_dependency_or_shell_cheat | -3 | loaded third-party import, socket, or process start | runtime audit | none (cheat negative) | pass |
| negative_reads_outside_input_dir | -3 | data-file read outside supplied input/output/stage/Python paths | runtime audit | none (cheat negative) | pass |
| negative_nondeterminism_source_in_solver | -3 | random/uuid/secrets import or clock call | AST import/call | none (cheat negative) | pass |
| negative_trusts_incumbent_objective | -3 | faulty objective literal without stronger answer cheat | AST exact constant | none (cheat negative) | pass |
| negative_writes_outside_output_dir | -3 | scratch/outside transient write, excluding input edits | runtime audit | none (cheat negative) | pass |

Each hidden row uses one output group on one independently reseeded input. The 7 groups have different artifact sets; H1-H4 have distinct data and goldens. The group comparator shares a helper but never pays twice for one observable. A3 warns at 36 checks; the hard cap is 70.

## Penalty acts

| Act | Test | Judge | Total |
|---|---|---|---:|
| Bake shipped total | hardcoded -5 | none | 5 |
| Embed six shipped identifiers without baked total | embedded -5 | none | 5 |
| Use non-stdlib module, socket, or child process | network/process -3 | none | 3 |
| Read external data file | outside-read -3 | none | 3 |
| Use clock or random source | nondeterminism -3 | none | 3 |
| Echo faulty objective without stronger answer cheat | incumbent -3 | none | 3 |
| Transient or lasting write outside output, apart from input | outside-write -3 | none | 3 |
| Modify /app/data in agent work | none | R8 -3 | 3 |
| Retrieve task-specific online answer material | none | R10 -3 | 3 |
| Claim a result contradicted by own artifacts/commands | none | R7 -5 | 5 |

The three answer-literal negatives stand down in priority order. The runtime write negative excludes input-dir writes, which R8 owns; the runtime read negative is a separate read act. Socket and asyncio subprocess audit events feed one -3 criterion.

## Shares and reflex

- Isolated hidden groups: coefficients, capital, quality = 28/101 = 27.72%. Composed hidden groups: plan, sourcing, totals, certificate = 72/101 = 71.29%. Shipped check = 1/101 = 0.99%.
- Tests 36 <= 70; judge 10 <= 70. Judge |negative| 11 <= positive 21. Test |negative| 25 <= positive 101.
- Reflex tests-only: before 17/101 = 0.1683, after 16/101 = 0.1584. Oracle 101/101 both.
- Single-lever losses (before -> after, points of 101): tie 69 -> 70, fallback 69 -> 70, amendment 69 -> 69, rejection normalization 32 -> 33, void-log 12 -> 13. H1-H4 separating cases retained.

STACKING PASS (the static AL-28 UNMATCHED hint is a classification artifact; the concrete acts above each cost at most 5).

## Lessons for the master

Static stacking hints should carry the input-set identity and classify negative acts by behavior; otherwise distinct H1-H4 groups and unrelated negatives appear duplicated.
