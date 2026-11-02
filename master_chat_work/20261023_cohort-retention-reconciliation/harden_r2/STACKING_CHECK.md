# STACKING_CHECK - cohort-retention-reconciliation, harden r2 (board 7cbd9f5)

Measured locally (09:30 IST 23 Oct) with the new `tests/test_output.py` loaded under a rewardkit stub, every check run against each program (`gates/score.py`, `gates/variants.py`). Levers: L1 green control (manifest), L2 identifiers vs strict fields (make-it-match), L3 refundable balance ledger, L4 segment weight override across files.

## (a) One row per test

Misread keys: L1a control sum over strictly parsed values; L1b no control check; L2none no normalisation; L2a normalise only events.csv; L2b raw-text duplicate key; L2c trim every field (the make-it-match repair); L3a uncapped subtraction; L3b balance on the raw id; L4a ignore weight_override; L4b segment of the raw id. "Fails" lists every single-lever misread that loses credit on that row (measured).

| test | w | observable | decisive logic | fails under |
|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | /app/out file set | 11 paths exist, JSON objects | none (shipped-only) |
| hidden_cohorts | 5 | cohorts.json, 3 hidden studies | whole doc equal, credit = share of studies | L2none L2a L2b L2c |
| hidden_retention | 5 | retention.json, 3 hidden studies | whole doc equal, share | L2none L2a L2b L2c |
| hidden_survival | 5 | survival.json, 3 hidden studies | whole doc equal, share | L2none L2a L2b L2c |
| hidden_revenue | 5 | revenue.json, 3 hidden studies | whole doc equal, share | L2none L2a L2b L2c L3a L3b L4a L4b |
| hidden_segments | 5 | segments.json, 3 hidden studies | whole doc equal, share | L2none L2a L2c L3a L3b L4a L4b |
| hidden_data_quality | 5 | data_quality.json, 3 hidden studies | whole doc equal (counts, control_mismatches, register), share | L1a L1b L2none L2a L2b L2c |
| hidden_reconciliation | 3 | reconciliation.json, 3 hidden studies | whole doc equal, share | L1a L2none L2a L2b L2c |
| hidden_study_audit | 5 | study_audit.json, 3 hidden studies | whole doc equal, share | L2none L2a |
| hidden_per_cohort_documents | 5 | cohort_<period>.json set, 3 hidden studies | file set and each doc equal, share | L2none L2a L2b L2c L3a L3b L4a L4b |
| hidden_serialization_is_canonical | 3 | text of every hidden doc | sorted keys, no float/bool, newline; needs full set + reference cohorts | L2none L2a L2b L2c |
| deterministic_rerun | 3 | bytes of two runs on one hidden study | byte-identical; needs full set + reference cohorts | L2none L2a L2b L2c |
| spaced_values_and_dates_are_malformed | 3 | data_quality.malformed_event_count, shipped + 4 rows | one figure equal | L2c |
| identifiers_match_across_files | 3 | cohorts.cohort_members, shipped + variant ids | one figure equal | L2none L2a |
| manifest_figures_follow_its_note | 3 | data_quality.control_mismatches, shipped + manifest edit | one figure equal | L1a L1b |
| balance_belongs_to_the_resolved_account | 3 | revenue.unhonored_cents, shipped + merge ledger | one figure equal | L3a L3b |
| segment_override_follows_the_resolved_account | 3 | revenue.weighted_revenue_total_cents, single fixture | one figure equal | L2c L4a L4b |
| mutation_override_moves_only_weighted_revenue | 3 | weighted total across override 7 and 11 | each equals its reference, total revenue unchanged | L2c L4a |
| mutation_minimum_moves_cohort_sizes | 3 | cohorts.cohort_sizes across minimum 0 and 100 | each equals its reference | L2none L2a |

TS-26: no two rows share both observable and logic. The two rows that read `weighted_revenue_total_cents` differ in logic (single fixture equality vs a mutation pair with an invariance assert); the whole-document rows each read a different document. Weights are on the kit's locked scale {1, 3, 5}; only the shipped-only presence check carries 1. TS-13: each row asserts one property; the whole-document rows assert only their own document, the fixture rows one figure.

Weight shares (71 positive, 19 checks): whole documents on hidden inputs 43 (60.6%), format and determinism on hidden inputs 6 (8.5%), isolated fixtures and mutations 21 (29.6%), shipped-only 1 (1.4%). Mutation tests: 2. No core weight is 1.

## (b) Penalty groups by triggering act

| act | tests channel | judge | sum of abs weight |
|---|---|---|---|
| emits the shipped answers on a fresh study (hard-coding) | negative_hardcoded_sample_answers -5 | none | 5 |
| output depends on the data directory's name | negative_filename_dependent_behaviour -5 (stands down when hard-coding fired) | none | 5 |
| reads /app/data beyond its argument | negative_reads_training_corpus_at_runtime -5 (stands down when hard-coding fired) | none | 5 |
| names verifier files (/tests, test_output, /logs/) | negative_reads_tests_or_reward_files -5 | none | 5 |
| third-party or network import | negative_external_dependency_or_network -3 | none | 3 |
| claims a check passed against its own output | none | N1 -5 | 5 |

Every group is at most 5 (AL-28). No negative grades a lever reading.

## (c) Cascade, measured

| program | tests-channel score | passes |
|---|---|---|
| oracle (solution/solve.py) | 1.0000 (71/71) | all |
| agent a2 program (reconstructed from trajectory step 11, `agent_prog_step11.py`) | **0.0563 (4/71)** | artifact_set 1, spaced_values 3 |
| S2 lazy (every lever reflex) | 0.0563 | artifact_set, spaced_values |
| S4 careful (L2a + L2b + L3b + L4b) | 0.1690 (12/71) | artifact_set, spaced_values, manifest, override mutation, reconciliation 2 of 3 studies |
| stub (empty objects) | 0.0141 | artifact_set |
| S3 L1a / L1b | 0.8451 / 0.8873 | |
| S3 L2none / L2a / L2b / L2c | 0.2394 / 0.2394 / 0.4648 / 0.2535 | |
| S3 L3a / L3b | 0.7465 / 0.7465 | |
| S3 L4a / L4b | 0.7042 / 0.7699 | |

The a2 program fails every hidden document on all three studies: it compares ids as raw text (L2none: upper-cased exclusion ids keep barred accounts, spaced `accounts.csv` ids become unknown, case-variant repeats survive dedup, title-cased rule lists stop qualifying events), writes no `control_mismatches` / `unhonored_cents` / `control_value_residual_cents` / `weight_overrides` (L1b), subtracts without a cap (L3a) and ignores `weight_override` (L4a). It fails every fixture except the strict-field one, which its strict regexes pass. a2 program score 0.0563 <= 0.20: PASS.
