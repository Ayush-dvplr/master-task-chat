# STACKING_CHECK redesign r2 (4d6dfe8): sensor-network-lsq-correlated-adjustment

Tool hints: `stacking_raw.txt` (stacking_check.py); corrections by reading the code are marked. Scores: tests channel, local, real `tests/test_output.py` (OUT/proto/score.py); judge not run.

## (a) Tests
| test | w | observable | decisive logic | levers whose misread fails it | a2 program |
|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped /app/out artifacts exist and parse | presence | - | pass |
| challenge_model_test_document | 3 | challenge: model_test.json + stage-2 figures | whole-document equality | B | fail |
| challenge_unknowns_documents | 3 | challenge: unknowns in 4 files | whole-document equality | B | fail |
| challenge_residual_documents | 3 | challenge: residual rows in 4 files + summary | whole-document equality | B | fail |
| challenge_observation_sets | 3 | challenge: removed/downweighted sets + final weights | whole-document equality | B | fail |
| challenge_rollup_documents | 3 | challenge: district/epoch/frame-campaign rollups | whole-document equality | B | fail |
| challenge_summary_reports | 3 | challenge: status/yaml/md/xml + trace | whole-document equality | B | fail |
| eval_model_test_document | 3 | eval: model_test.json + stage-2 figures | whole-document equality | A | fail |
| eval_unknowns_documents | 3 | eval: unknowns in 4 files | whole-document equality | A | fail |
| eval_residual_documents | 3 | eval: residual rows in 4 files + summary | whole-document equality | A | fail |
| eval_observation_sets | 3 | eval: removed/downweighted sets + final weights | whole-document equality | A | fail |
| eval_rollup_documents | 3 | eval: district/epoch/frame-campaign rollups | whole-document equality | A | fail |
| eval_summary_reports | 3 | eval: status/yaml/md/xml + trace | whole-document equality | A | fail |
| audit_model_test_document | 3 | audit: model_test.json + stage-2 figures | whole-document equality | C | fail |
| audit_unknowns_documents | 3 | audit: unknowns in 4 files | whole-document equality | C | fail |
| audit_residual_documents | 3 | audit: residual rows in 4 files + summary | whole-document equality | C | fail |
| audit_observation_sets | 3 | audit: removed/downweighted sets + final weights | whole-document equality | C | fail |
| audit_rollup_documents | 3 | audit: district/epoch/frame-campaign rollups | whole-document equality | C | fail |
| audit_summary_reports | 3 | audit: status/yaml/md/xml + trace | whole-document equality | C | fail |
| control_values_on_hidden_extracts | 3 | control fields of adjusted_state/datum/provenance, 3 extracts | value equality | - | pass |
| superseded_records_on_hidden_extracts | 3 | provenance superseded_records, 3 extracts | list equality | - | pass |
| canonical_serialization_on_hidden_extracts | 1 | every JSON artifact, 3 extracts | sorted keys + newline | - | pass |
| traverse_closure_rows_shipped | 3 | shipped residual/weight rows of absorbing lengths | owned rows | - | fail |
| eval_traverse_closure_rows_hard | 5 | eval residual/weight rows of absorbing lengths | owned rows | A | fail |
| centring_chain_rows_shipped | 3 | shipped rows of lengths on set-out stations | owned rows | - | fail |
| challenge_centring_chain_rows_hard | 5 | challenge rows of lengths on set-out stations | owned rows | B | fail |
| district_rollups_shipped | 3 | shipped district_*.json | document equality | - | fail |
| audit_district_rows_hard | 5 | audit district_*.json + rows of relabelled records | document + owned rows | C | fail |
| negative_hardcoded_sample_answers | -5 | program literals | >= 2 shipped answer tokens | - (does not fire) | not fired |
| negative_external_dependency | -3 | program imports | numpy/scipy/pandas | - (does not fire) | not fired |

No two rows share observable and logic (tool: TS-26 none). Each `_hard` test reads only its rule's own rows, not the family documents. The TS-13 hint on control_values (14 asserts) is the kept minor from p12_r3, unchanged.

## (b) Penalty groups (tests + judge)
| act | members | sum abs w | verdict |
|---|---|---|---|
| hardcoding shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| third-party numeric import | negative_external_dependency -3 | 3 | PASS |
| reply figure disagreeing with artifacts | R6 -5 | 5 | PASS |
| claiming a check passed that never ran | R7 -5 | 5 | PASS |
| program opens a path outside its two dirs | R8 -3 | 3 | PASS |

Correction: the tool grouped R6 and R8 as one "UNMATCHED" act (8, FAIL); they are different acts, each <= 5. No negative grades a lever.

## (c) Weight shares (positive 86)
Hidden reruns 76/86 = 88.4% (G3 PASS): 54 whole-document family checks, 15 owned `_hard` rows, 7 isolated. Shipped-only 10/86 = 11.6% (artifact 1, three visible lever tests 9). Weight-1 checks are not core. Tests 30, judge criteria 11 (positive 24; R5 J4 code quality, R9-R11 recompute conduct; the tool's "J2 conduct none" hint is wrong).

## (d) Cost table (G10), real tests
| row | tests | lost |
|---|---|---|
| oracle | 86/86 | 0 |
| A alone (second closure sharing re-enters the fits test) | 63/86 = 0.733 | 23 (26.7%) |
| B alone (set-out one mark deep) | 63/86 = 0.733 | 23 (26.7%) |
| C alone (district = line region) | 63/86 = 0.733 | 23 (26.7%) |
| any two | 40/86 = 0.465 | 46 |
| all three | 17/86 = 0.198 | 69 |

Each alone >= 25% PASS; one-fact-wrong 26.7% (CL-4 band). Overall for a one-lever slip is 81.6 at rubric 90 and needs judge <= 66 to fall under 70 (WORK/COST_TABLE.md). Final-generator differential fuzz (OUT/proto/fuzz_final_300.json, 300 fresh seeds per lever, every artifact byte-compared): A reflex differs 300/300, B 300/300, C 300/300; a2 program 300/300 each; 0 generator rejects, 0 oracle failures. Shipped extract: identical figures under every variant (W5).

## (e) Rule coverage (G11)
WORK/RULE_COVERAGE.md: 33 rows, none with 0 tests failed.

## Reflex gate (section 6)
a2 program on the new tests: 8/86 = 0.093 (<= 0.20 PASS). It passes artifact_set, control_values, superseded_records, canonical and fails every hidden family check and all six lever tests.

STACKING PASS
