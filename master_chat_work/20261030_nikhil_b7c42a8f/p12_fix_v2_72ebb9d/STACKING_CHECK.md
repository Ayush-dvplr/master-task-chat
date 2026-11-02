# STACKING_CHECK 72ebb9d (b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042, tree c2c53493843d)

Tool output (master_chat_tasks/tools/stacking_check.py on BUNDLE after all edits):

```
# stacking_check: b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042

tests/test_output.py: 31 checks, positive total 64, negatives -23; judge: 33 criteria, positive 65, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| ledger_backbone_exact | 5 | shipped_only (artifact/shipped wording) | shipped, ledger_backbone, digests | _delivered, _expected, _digest | 0/0 |
| ledger_spine_exact | 5 | shipped_only (artifact/shipped wording) | shipped, ledger_spine, digests | _delivered, _expected, _digest | 0/0 |
| lob_cycle_capacity_and_fill_exact | 5 | isolated (default (rule/fixture/case check)) | shipped, cells, digests | _delivered, _views, _expected | 0/0 |
| program_reproduces_unseen_extract_alpha | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | A, digests, out, code ... | _run, _digests, _complete | 0/0 |
| program_reproduces_unseen_extract_beta | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | B, digests, out, code ... | _run, _digests, _complete | 0/0 |
| cross_artifact_identity_triangle_holds | 1 | shipped_only (artifact/shipped wording) | treaty_working.json | _delivered | 0/0 |
| row_order_permutation_changes_nothing | 3 | mutation (mutation in name or description lead) | A_perm, digests, out, A ... | _run, _digests, _complete | 0/0 |
| outcome_and_reason_vocabulary_exact | 3 | isolated (default (rule/fixture/case check)) | .json | _delivered, _expected, _digest | 0/0 |
| methodology_audit_attachment_exact | 3 | isolated (default (rule/fixture/case check)) | errata_2032-04.md, methodology_audit.json | _delivered, _str_eq | 0/0 |
| data_quality_source_counts_exact | 3 | isolated (default (rule/fixture/case check)) | data_quality.json | _delivered, _expected, _int_eq | 0/0 |
| data_quality_anomaly_tallies_exact | 3 | isolated (default (rule/fixture/case check)) | data_quality.json | _delivered, _expected, _int_eq | 0/0 |
| treaty_layer_breakdown_exact | 3 | isolated (default (rule/fixture/case check)) | treaty_working.json | _delivered, _expected, _int_eq | 0/0 |
| summary_claim_counts_exact | 3 | isolated (default (rule/fixture/case check)) | summary.json | _delivered, _expected, _int_eq | 0/0 |
| chain_ladder_development_exact | 3 | isolated (default (rule/fixture/case check)) | .json | _delivered, _expected, _digest | 0/0 |
| hidden_extract_outcomes_exact | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | A, B, ledger_outcome, code ... | _expected, _run, _digest | 0/0 |
| hidden_extract_quality_tallies_exact | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | data_quality.json | _expected, _run, _complete | 0/0 |
| byte_identical_rerun | 1 | shipped_only (format check, no hidden-input wording) | A, artifact_bytes | _rerun_bytes | 0/0 |
| exact_serialization_format | 1 | shipped_only (format check, no hidden-input wording) | utf-8 | _delivered | 0/0 |
| artifacts_present_and_parse | 1 | shipped_only (artifact/shipped wording) | .json | _delivered, _complete, _module | 0/0 |
| program_runs_and_exits_clean | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | A, code, out | _run, _complete | 0/1 |
| methodology_audit_holds_only_declared_sections | 1 | isolated (default (rule/fixture/case check)) | methodology_audit.json | _all_keys, _delivered | 0/0 |
| methodology_audit_remaining_sections_exact | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | methodology_audit.json | _expected, _run, _delivered | 0/0 |
| summary_and_treaty_values_exact | 1 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | A, B, summary_values, digests ... | _expected, _digest, _run | 0/0 |
| module_imports_only_standard_library | 1 | isolated (default (rule/fixture/case check)) | . | _source | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | - | - | 0/0 |
| negative_embedded_corpus_rows | -5 | negative (weight < 0 or negative_ name) | CLM-00, RE-0, AY20 | _safe, _literals, _source | 0/2 |
| negative_output_independent_of_the_corpus | -3 | negative (weight < 0 or negative_ name) | A, B, code, out | _safe, negative_embedded_corpus_rows, _run | 0/0 |
| negative_module_reads_a_fixed_corpus_path | -3 | negative (weight < 0 or negative_ name) | A, A_named, code, out | _run, _digests, _complete | 0/0 |
| negative_silent_recovery_from_missing_source | -3 | negative (weight < 0 or negative_ name) | A_missing, A, out, ledger_backbone ... | _run, _matches, _complete | 0/0 |
| negative_module_mutates_the_corpus | -3 | negative (weight < 0 or negative_ name) | A, before, after, code | _run | 0/0 |
| negative_module_opens_network_or_shells_out | -1 | negative (weight < 0 or negative_ name) | socket, urllib, http, requests ... | _source, _module | 0/2 |

TS-26 duplicate candidates (same observable AND same logic): data_quality_source_counts_exact = data_quality_anomaly_tallies_exact

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| UNMATCHED act (name it by hand) | negative_embedded_corpus_rows -5, negative_output_independent_of_the_corpus -3, negative_module_reads_a_fixed_corpus_path -3, negative_silent_recovery_from_missing_source -3, negative_module_mutates_the_corpus -3 | R29 -5, R30 -3, R31 -3, R32 -3 | 31 | FAIL |
| third-party or network import | negative_module_opens_network_or_shells_out -1 | - | 1 | PASS |
| naming or reading grader files | - | R27 -5 | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | R28 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 19 (29.7%)
- isolated: 28 (43.8%)
- mutation: 3 (4.7%)
- shipped_only: 14 (21.9%)
- G3: hidden or mutated reruns 34.4% (>= 30%); isolated+mutation 48.4%, whole-document 0.0%, shipped-only 21.9% (info, no cap)

## 5. Caps and weights

- tests 31, criteria 33 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): cross_artifact_identity_triangle_holds, hidden_extract_quality_tallies_exact, byte_identical_rerun, exact_serialization_format, artifacts_present_and_parse, program_runs_and_exits_clean, methodology_audit_holds_only_declared_sections, summary_and_treaty_values_exact, module_imports_only_standard_library
- judge J1 hints (criterion quotes a figure): R1, R2, R3, R4, R5, R6, R7, R9, R12, R13, R14, R18, R19, R32, R33
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 1 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 34.4% PASS
- G3 isolated / shipped-only (info, no cap): 48.4% / 21.9%
- tests >= 10 (no cap): 31 PASS
- criteria >= 8 (no cap): 33 PASS
- judge mode batched: batched
```

## By-hand notes

- TS-26 duplicate candidate data_quality_source_counts_exact = data_quality_anomaly_tallies_exact: not a duplicate. The first reads 4 source keys (late_recorded, cross_source_collapsed, unknown_reinsurer_rows, out_of_horizon_rows), the second the other 8 data_quality keys. Pre-existing, not flagged by QC.
- AL-28 "UNMATCHED act" row (31, FAIL) is a tool artefact: it lumps distinct acts. Embedded corpus copy, output independent of the corpus, fixed corpus path, silent recovery from a missing source, corpus mutation, curve contradicted (R29), range or tilde (R30), online answers (R31), numeric-literal factor (R32) are separate cheats. The one real stack found by hand (embedded copy also firing output-independent) is fixed: negative_output_independent_of_the_corpus stands down when negative_embedded_corpus_rows fires (test_output.py:899), and the embedded negative stands down when negative_hardcoded_sample_answers fires (G05-4).
- Honesty group now R28 -5 only (old R33 -5 dropped): PASS. G3 hidden or mutated reruns 34.4%: PASS (before 27.5%).
