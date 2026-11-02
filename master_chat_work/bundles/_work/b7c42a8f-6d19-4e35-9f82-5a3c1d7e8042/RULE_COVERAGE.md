# RULE_COVERAGE (AL-27, G05-5)

Triggers live in hidden extracts A and B only (shipped corpus unchanged). Mutants patch one line of solution/solve.py; graded with the fixed tests/ in Docker (warm-b7c-tests2, runs/cov/grades.jsonl, oracle 69/69).

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| paren_negatives (parenthesised amount, CLM-00002 col 7 in A and B) | environment/data/data_quality_counting.md:45 | R_paren_negative: regex `\(\d[\d,]*\)` -> `\(-\d+\)` | 1 (hidden_extract_quality_tallies_and_outcomes_exact) |
| block_unit_rows (fixed-width paid whole thousands, CLM-00001 in A and B) | environment/data/data_quality_counting.md:41 | R_block_unit: `% 1000 == 0` -> `== 1` | 1 (hidden_extract_quality_tallies_and_outcomes_exact) |
| duplicate_identical (byte-identical CLM-00162 rows in A and B) | environment/data/data_quality_counting.md:9 | R_identical_duplicate: count forced to 0 | 1 (hidden_extract_quality_tallies_and_outcomes_exact) |
| gap_shifted (cycle gap: A H10, B H16) | environment/data/data_quality_counting.md:25 | R_cycle_gap: instant in no window not moved to next cycle | 5 (hidden_extract_quality_tallies_and_outcomes_exact, methodology_audit_remaining_sections_exact, program_reproduces_unseen_extract_alpha, program_reproduces_unseen_extract_beta, row_order_permutation_changes_nothing) |
| ZERO / CAP_ZERO (zero-capacity cell: A (cal,H05), B (gl,H07)) | environment/data/allocation_rules.md:35 | R_zero_capacity: `if cap == 0:` -> `if False:` | 1 (hidden_extract_quality_tallies_and_outcomes_exact) |
| ZERO / NO_QUALIFIED_LAYER (CLM-00161 nothing to cede in A and B) | environment/data/allocation_rules.md:38 | R_no_qualified_layer: reason -> `NONE` | 1 (hidden_extract_quality_tallies_and_outcomes_exact) |

## Update 72ebb9d (QC v2): regraded on current tests (P 64), runs/cov_v2/grades.jsonl, oracle 64/64

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| paren_negatives | environment/data/data_quality_counting.md:45 | R_paren_negative | 1 (hidden_extract_quality_tallies_exact) |
| block_unit_rows | environment/data/data_quality_counting.md:41 | R_block_unit | 1 (hidden_extract_quality_tallies_exact) |
| duplicate_identical | environment/data/data_quality_counting.md:9 | R_identical_duplicate | 1 (hidden_extract_quality_tallies_exact) |
| gap_shifted | environment/data/data_quality_counting.md:25 | R_cycle_gap | 6 (hidden_extract_outcomes_exact, hidden_extract_quality_tallies_exact, methodology_audit_remaining_sections_exact, alpha, beta, row_order_permutation_changes_nothing) |
| ZERO / CAP_ZERO | environment/data/allocation_rules.md:35 | R_zero_capacity | 1 (hidden_extract_outcomes_exact) |
| ZERO / NO_QUALIFIED_LAYER | environment/data/allocation_rules.md:38 | R_no_qualified_layer | 1 (hidden_extract_outcomes_exact) |
| RETRACTED over EXCLUDED/UNRESOLVABLE_CHAIN (G05-3: extract B retracts unresolved CLM-00014) | environment/data/allocation_rules.md:29-38, reason_codes.json outcome_precedence | R_retract_over_excluded: retraction honoured only when the reinsurer resolves | 3 (hidden_extract_outcomes_exact, program_reproduces_unseen_extract_beta, summary_and_treaty_values_exact) |

## Update 2990713 (QC v3): regraded on current tests (P 64), runs/cov_v3/grades.jsonl, oracle 64/64

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| paren_negatives | environment/data/data_quality_counting.md:45 | R_paren_negative | 1 (hidden_extract_quality_tallies_exact) |
| block_unit_rows | environment/data/data_quality_counting.md:41 | R_block_unit | 1 (hidden_extract_quality_tallies_exact) |
| duplicate_identical | environment/data/data_quality_counting.md:9 | R_identical_duplicate | 1 (hidden_extract_quality_tallies_exact) |
| gap_shifted | environment/data/data_quality_counting.md:25 | R_cycle_gap | 6 (hidden_extract_outcomes_exact, hidden_extract_quality_tallies_exact, methodology_audit_remaining_sections_exact, alpha, beta, row_order_permutation_changes_nothing) |
| ZERO / CAP_ZERO | environment/data/allocation_rules.md:35 | R_zero_capacity | 1 (hidden_extract_outcomes_exact) |
| ZERO / NO_QUALIFIED_LAYER | environment/data/allocation_rules.md:38 | R_no_qualified_layer | 1 (hidden_extract_outcomes_exact) |
| RETRACTED over EXCLUDED/UNRESOLVABLE_CHAIN (extract B) | environment/data/reason_codes.json outcome_precedence | R_retract_over_excluded | 3 (hidden_extract_outcomes_exact, program_reproduces_unseen_extract_beta, summary_and_treaty_values_exact) |
| EXCLUDED over ZERO (G05-3: extract A puts unresolved CLM-00014 in zero-capacity cell gl,H11) | environment/data/reason_codes.json outcome_precedence | R_zero_over_excluded: excluded row enters allocation | 2 (hidden_extract_outcomes_exact, outcome_and_reason_vocabulary_exact) |

## Update 841c07e (QC v4)
No data, solve.py or rule-check change this round; the rows of the 2990713 table stand (tests P 64 unchanged for these checks). New deterministic coverage: the settlement section (closed vocabularies in environment/data/alae_rules.md and discounting_rules.md) is now compared by methodology_audit_remaining_sections_exact on shipped, A and B; mutants hyg_alae (alae_convention -> excess_only) and hyg_curve (discount_curve -> flat_10y) each lose exactly that check (runs/hyg_v4/grades.jsonl, 61/64). The output-scope sentence (instruction.md:7) is a process rule, graded by judge R35 (trajectory), not a data rule, so it has no triggering-input row.

## Update dbe00fc (QC v5)
Settlement fixtures (AL-27 G05-1): extract A's `claim_adjustment_log.log` settles `excess_only`, extract B's `treasury_curve_observations.log` settles `flat_10y`; the shipped corpus stays `pro_rata` / `duration_matched` (bytes unchanged). Unique fit by independent script `unique_fit.py` (runs/unique_fit_v6/out.jsonl): shipped alae pro_rata only (fraction 0.08), curve duration_matched only; A alae excess_only only (no pro_rata fraction fits), curve duration_matched; B alae pro_rata only, curve flat_10y only (max dev flat 0.0, duration 0.016259). Mutants on the fixed tests (runs/cov_v6, runs/hyg_v6, P 64):

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| ALAE convention settled from the log | environment/data/alae_rules.md:3 | R_alae_skip_settle (settle returns pro_rata, 0.08) | 5 (hidden_extract_outcomes_exact, methodology_audit_remaining_sections_exact, program_reproduces_unseen_extract_alpha, row_order_permutation_changes_nothing, summary_and_treaty_values_exact; 15 points) |
| excess_only fit test (retention rows zero) | environment/data/alae_rules.md:7 | R_alae_reversed (excess_only test inverted) | 9 (byte_identical_rerun, hidden_extract_outcomes_exact, hidden_extract_quality_tallies_exact, methodology_audit_remaining_sections_exact, program_reproduces_unseen_extract_alpha, program_runs_and_exits_clean, row_order_permutation_changes_nothing, summary_and_treaty_values_exact, summary_run_fields_exact) |
| unlogged claim ALAE under the settled convention | environment/data/alae_rules.md:5,9 | hard_alae (main hard-codes pro_rata, 0.08) | 5 (same as R_alae_skip_settle; 15 points) |
| discount curve settled from the log | environment/data/discounting_rules.md:3 | R_curve_skip_settle / hard_curve (returns duration_matched) | 1 (methodology_audit_remaining_sections_exact; 3 points) |
| flat_10y / duration_matched fit test | environment/data/discounting_rules.md:5 | R_curve_reversed (fit names swapped) | 1 (methodology_audit_remaining_sections_exact; 3 points) |
| settlement words typed in | environment/data/output_contract.md:19 | hard_words (audit strings pro_rata / duration_matched) | 1 (methodology_audit_remaining_sections_exact; 3 points) |

No 0 row. The pre-v5 rows above stand (cov_v6 reproduces them on the fixed tests).
