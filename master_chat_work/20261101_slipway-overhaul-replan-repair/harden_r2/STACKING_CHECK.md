# STACKING_CHECK (harden r2, bddb388)

Command: `python3 master_chat_tasks/tools/stacking_check.py <BUNDLE> --classes '<json>'` (run 2026-11-01 15:11 IST, final 110-point tests).
Class overrides, each confirmed by reading the code: the five `package_*` minted-round checks compare whole documents on
hidden minted rounds (`_minted`, whole_doc); the twelve `package_crosswalk_*` checks drive the delivered engine on held-out
rounds written by `write_corpus(dest, seed, legacy)` (`_held`, hidden_rows); `shipped_amendment_classification_exact`
reads only the delivered shipped-round documents (shipped_only). Overrides: `{"package_eval_state_exact": "whole_doc", "package_eval_cascade_exact": "whole_doc", "package_challenge_state_exact": "whole_doc", "package_challenge_cascade_exact": "whole_doc", "package_probe_publication_exact": "whole_doc", "package_crosswalk_groups_state_exact": "hidden_rows", "package_crosswalk_groups_cascade_exact": "hidden_rows", "package_crosswalk_groups_publication_exact": "hidden_rows", "package_crosswalk_rules_state_exact": "hidden_rows", "package_crosswalk_rules_cascade_exact": "hidden_rows", "package_crosswalk_rules_publication_exact": "hidden_rows", "package_crosswalk_amendments_state_exact": "hidden_rows", "package_crosswalk_amendments_cascade_exact": "hidden_rows", "package_crosswalk_amendments_publication_exact": "hidden_rows", "package_crosswalk_every_state_exact": "hidden_rows", "package_crosswalk_every_cascade_exact": "hidden_rows", "package_crosswalk_every_publication_exact": "hidden_rows", "shipped_amendment_classification_exact": "shipped_only"}`

## TS-26 by hand (the tool groups by helper, not by observable)

| tool group | distinct observable each check pays | verdict |
|---|---|---|
| eleven `shipped_*` | one document family each of the shipped round: identifier 01,04,06; graph 02,03,19; closure 07,08; rule 05,10; baseline 09,11,12; classification 13; invalidation 14; ledger 15,16; store 17; final 18,20,21; audit 22-25 | distinct, PASS (bodies unchanged) |
| five `package_*` minted | eval_state and eval_cascade share EVAL_SEED with disjoint families (STATE vs CASCADE); challenge pair likewise on CHALLENGE_SEED; probe_publication on PROBE_SEED, PUBLICATION family, papers first on the command line | distinct, PASS (bodies unchanged) |
| twelve `package_crosswalk_*` | eleven held-out rounds (tests/test_output.py:4905-4915). groups x state/cascade/publication on HELD_GROUPS, HELD_GROUPS_CASCADE, HELD_GROUPS_PUBLISHED (legacy ids in slot groups); rules x three on HELD_RULES, HELD_RULES_CASCADE, HELD_RULES_PUBLISHED (legacy ids in charge rules); amendments_state (01,04-12,18-20) and amendments_cascade (13-17,21) share HELD_AMENDMENTS with disjoint documents, amendments_publication on HELD_AMENDMENTS_PUBLISHED; every x three on HELD_EVERY (STATE), HELD_EVERY_CASCADE (CASCADE), HELD_PUBLISHED (PUBLICATION). Doc 24 digests every doc, so each publication check has a round no other check reads | distinct, PASS |

Kill evidence of separation (score5.log): a3_groups keeps the three groups checks only (15), a3_rules the three rules
checks only (15), a3_amendments the three amendments checks only (15); each oracle_less_* loses its three place checks
and the three every checks (80/110). One fault pays only the checks whose round carries it.

## AL-28 by hand (the tool's UNMATCHED bucket holds sixteen different acts)

| act | layer | weight |
|---|---|---|
| shift length taken flat (480) | tests | -5 |
| pool weights taken flat | tests | -5 |
| deferral rate from the rescinded sitting | tests | -5 |
| drafting register read as the register in force | tests | -3 |
| capacity boundary read as strict | tests | -3 |
| set ranked on charge alone | tests | -5 |
| rebate taken before the surcharges | tests | -3 |
| penalty charged on every job | tests | -3 |
| cascade stopped at the first hop | tests | -5 |
| cascade never stopped | tests | -3 |
| withdrawal treated as inert | tests | -3 |
| package ignores its input | tests | -3 |
| final message states a figure other than its delivered file (R15) | judge | -5 |
| final message states a check larger than the run shows (R16) | judge | -3 |
| final message reports a withdrawn job as standing (R17) | judge | -3 |
| agent edited the working papers under /app/data (R18) | judge | -3 |

Each row is one act with one penalty in one layer; no act exceeds 5. Matched groups from the tool (rebinds, hardcoding,
nondeterminism, file names, training corpus, R14 honesty) each PASS at <= 5.

## Weight shares
G3 hidden or mutated reruns 69.1% PASS. Weight-1 checks are the two structural ones only (TS-20).
Lever: twelve crosswalk checks x 5 = 60 of 110 positive (54.5%). Old core checks re-weighted 5 -> 3 (3 stays 3):
weight-only change, bodies byte-identical except the Q1/Q2/Q8 reference fixes; old positive 68 -> 50.

## Tool output (verbatim)

# stacking_check: slipway-overhaul-replan-repair

tests/test_output.py: 47 checks, positive total 110, negatives -63; judge: 18 criteria, positive 39, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| delivered_documents_present_and_parse | 1 | whole_doc (whole-document wording) | .json, .jsonl, .csv, .tsv ... | _delivered | 5/0 |
| delivered_package_shape | 1 | shipped_only (artifact/shipped wording) | project.zip | _engine_root, _scratch, _corpus | 6/1 |
| shipped_identifier_layer_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_graph_layer_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_closure_and_demand_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_rule_and_charge_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_baseline_optimum_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_amendment_classification_exact | 3 | shipped_only (override) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_invalidation_sets_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_work_ledger_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_store_summary_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_final_optimum_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| shipped_audit_documents_exact | 3 | shipped_only (artifact/shipped wording) | the shipped round | _reference, _compare, _delivered | 0/0 |
| package_eval_state_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_eval_cascade_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_challenge_state_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_challenge_cascade_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_probe_publication_exact | 3 | whole_doc (override) | the minted round, name:, carries documents the contract does not, , | _case, _compare, _reference | 0/0 |
| package_crosswalk_groups_state_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_rules_state_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_amendments_cascade_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_amendments_state_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_every_state_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_every_publication_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_groups_cascade_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_groups_publication_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_rules_cascade_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_rules_publication_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_amendments_publication_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| package_crosswalk_every_cascade_exact | 5 | hidden_rows (override) | held-case, held, the held-out round, name: ... | _compare, _drive, _held_reference | 0/0 |
| negative_shift_length_taken_flat | -5 | negative (weight < 0 or negative_ name) | R_FLAT_SHIFT | _detector | 0/0 |
| negative_pool_weights_taken_flat | -5 | negative (weight < 0 or negative_ name) | R_LEGACY_WEIGHTS | _detector | 0/0 |
| negative_deferral_rate_from_the_rescinded_sitting | -5 | negative (weight < 0 or negative_ name) | R_RESCINDED_MEMO | _detector | 0/0 |
| negative_drafting_register_read | -3 | negative (weight < 0 or negative_ name) | R_CURRENT_REGISTER | _detector | 0/0 |
| negative_capacity_boundary_read_as_strict | -3 | negative (weight < 0 or negative_ name) | R_STRICT_CAPACITY | _detector | 0/0 |
| negative_set_ranked_on_charge_alone | -5 | negative (weight < 0 or negative_ name) | R_COST_ONLY | _detector | 0/0 |
| negative_rebate_taken_before_the_surcharges | -3 | negative (weight < 0 or negative_ name) | R_REBATE_BEFORE | _detector | 0/0 |
| negative_penalty_charged_on_every_job | -3 | negative (weight < 0 or negative_ name) | R_PENALTY_ALL | _detector | 0/0 |
| negative_cascade_stopped_at_the_first_hop | -5 | negative (weight < 0 or negative_ name) | R_SHALLOW_CASCADE | _detector | 0/0 |
| negative_cascade_never_stopped | -3 | negative (weight < 0 or negative_ name) | R_NO_CUTOFF | _detector | 0/0 |
| negative_withdrawal_treated_as_inert | -3 | negative (weight < 0 or negative_ name) | R_REMOVAL_INERT | _detector | 0/0 |
| negative_rebinds_verifier_dependencies | -3 | negative (weight < 0 or negative_ name) | the archive shadows no verifier dependency, sitecustomize, usercustomize, conftest ... | _engine_root | 1/2 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | the shipped record is wrong; this detector stays silent | _reference, _case, _delivered | 1/0 |
| negative_package_ignores_its_input | -3 | negative (weight < 0 or negative_ name) | 18_final_selection.json | _reference, _case | 1/0 |
| negative_nondeterministic_output | -3 | negative (weight < 0 or negative_ name) | repeat | _case, _drive, _corpus | 1/0 |
| negative_filename_dependent_behaviour | -3 | negative (weight < 0 or negative_ name) | repeat, papers_under_another_name, renamed-run, renamed ... | _case, _drive, _corpus | 1/0 |
| negative_reads_training_corpus_at_runtime | -3 | negative (weight < 0 or negative_ name) | 18_final_selection.json | _scratch, _drive, _corpus | 1/0 |

TS-26 duplicate candidates (same observable AND same logic): shipped_identifier_layer_exact = shipped_graph_layer_exact = shipped_closure_and_demand_exact = shipped_rule_and_charge_exact = shipped_baseline_optimum_exact = shipped_amendment_classification_exact = shipped_invalidation_sets_exact = shipped_work_ledger_exact = shipped_store_summary_exact = shipped_final_optimum_exact = shipped_audit_documents_exact; package_eval_state_exact = package_eval_cascade_exact = package_challenge_state_exact = package_challenge_cascade_exact = package_probe_publication_exact; package_crosswalk_groups_state_exact = package_crosswalk_rules_state_exact = package_crosswalk_amendments_cascade_exact = package_crosswalk_amendments_state_exact = package_crosswalk_every_state_exact = package_crosswalk_every_publication_exact = package_crosswalk_groups_cascade_exact = package_crosswalk_groups_publication_exact = package_crosswalk_rules_cascade_exact = package_crosswalk_rules_publication_exact = package_crosswalk_amendments_publication_exact = package_crosswalk_every_cascade_exact

## 2. TS-13 multi-assert hints

- delivered_documents_present_and_parse: 5 asserts, 0 and-chained comparisons
- delivered_package_shape: 6 asserts, 1 and-chained comparisons

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| UNMATCHED act (name it by hand) | negative_shift_length_taken_flat -5, negative_pool_weights_taken_flat -5, negative_deferral_rate_from_the_rescinded_sitting -5, negative_drafting_register_read -3, negative_capacity_boundary_read_as_strict -3, negative_set_ranked_on_charge_alone -5, negative_rebate_taken_before_the_surcharges -3, negative_penalty_charged_on_every_job -3, negative_cascade_stopped_at_the_first_hop -5, negative_cascade_never_stopped -3, negative_withdrawal_treated_as_inert -3, negative_package_ignores_its_input -3 | R15 -5, R16 -3, R17 -3, R18 -3 | 60 | FAIL |
| rebinds verifier dependencies | negative_rebinds_verifier_dependencies -3 | - | 3 | PASS |
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| nondeterministic output | negative_nondeterministic_output -3 | - | 3 | PASS |
| output depends on file names | negative_filename_dependent_behaviour -3 | - | 3 | PASS |
| reads data beyond its argument | negative_reads_training_corpus_at_runtime -3 | - | 3 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R14 -3 | 3 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 16 (14.5%)
- format_hidden: 0 (0.0%)
- hidden_rows: 60 (54.5%)
- isolated: 0 (0.0%)
- mutation: 0 (0.0%)
- shipped_only: 34 (30.9%)
- G3: hidden or mutated reruns 69.1% (>= 30%); isolated+mutation 0.0%, whole-document 14.5%, shipped-only 30.9% (info, no cap)

## 5. Caps and weights

- tests 47, criteria 18 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): delivered_documents_present_and_parse, delivered_package_shape
- judge J1 hints (criterion quotes a figure): none
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 3 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 69.1% PASS
- G3 isolated / shipped-only (info, no cap): 0.0% / 30.9%
- tests >= 10 (no cap): 47 PASS
- criteria >= 8 (no cap): 18 PASS
- judge mode batched: batched

## Lessons for the master
- the tool groups checks by helper, so held-out checks on separate rounds read as TS-26 candidates; a round-per-check table settles it | no change: by-hand table is the intended route
