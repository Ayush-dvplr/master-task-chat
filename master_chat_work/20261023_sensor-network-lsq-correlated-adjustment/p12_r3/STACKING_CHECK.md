# STACKING_CHECK: sensor-network-lsq-correlated-adjustment

Live kit 71a653b2, P12 r3 (board 078d40a). The script's raw hints are in `stacking_raw.txt`, byte-identical to the r2 raw output because no test, weight or penalty changed this round (only judge R5 wording, a positive conduct criterion at weight 3, and TRUTH.md prose); the classes and penalty acts below are corrected from the test and judge bodies.

## Tests

| Test | Weight | Observable | Decisive logic | Wrong readings failed | v0 reflex |
|---|---:|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped artifact set and JSON parse | existence and parse | none | fail |
| challenge_model_test_document | 3 | challenge: model_test_document | _check_model_test | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| challenge_unknowns_documents | 3 | challenge: unknowns_documents | _check_unknowns | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| challenge_residual_documents | 3 | challenge: residual_documents | _check_residuals | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| challenge_observation_sets | 3 | challenge: observation_sets | _check_sets | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| challenge_rollup_documents | 3 | challenge: rollup_documents | _check_rollups | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN, V0-11 | fail |
| challenge_summary_reports | 3 | challenge: summary_reports | _check_reports | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| eval_model_test_document | 3 | eval: model_test_document | _check_model_test | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| eval_unknowns_documents | 3 | eval: unknowns_documents | _check_unknowns | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| eval_residual_documents | 3 | eval: residual_documents | _check_residuals | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| eval_observation_sets | 3 | eval: observation_sets | _check_sets | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| eval_rollup_documents | 3 | eval: rollup_documents | _check_rollups | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN, V0-11 | fail |
| eval_summary_reports | 3 | eval: summary_reports | _check_reports | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| audit_model_test_document | 3 | audit: model_test_document | _check_model_test | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| audit_unknowns_documents | 3 | audit: unknowns_documents | _check_unknowns | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| audit_residual_documents | 3 | audit: residual_documents | _check_residuals | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| audit_observation_sets | 3 | audit: observation_sets | _check_sets | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| audit_rollup_documents | 3 | audit: rollup_documents | _check_rollups | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN, V0-11 | fail |
| audit_summary_reports | 3 | audit: summary_reports | _check_reports | H1-CENTRING, H2-ANGLE-REDUCE, H3-REVISION, H4-CHAIN | fail |
| control_values_on_hidden_extracts | 3 | control values and source across hidden extracts | _check_control_values | V0-6 | fail |
| superseded_records_on_hidden_extracts | 3 | superseded records across hidden extracts | _check_superseded_records | H3-REVISION | fail |
| canonical_serialization_on_hidden_extracts | 1 | JSON byte form across hidden extracts | _check_canonical_serialization | none | fail |
| negative_hardcoded_sample_answers | -5 | cheat act in delivered program | source audit after clean hidden run | none | fail |
| negative_external_dependency | -3 | cheat act in delivered program | source audit after clean hidden run | none | fail |

## Penalty acts and overlap

| Act | Test | Judge | Absolute weight | Verdict |
|---|---:|---:|---:|---|
| Shipped-answer hardcoding | -5 | 0 | 5 | PASS |
| Third-party numeric import | -3 | 0 | 3 | PASS |
| Final message contradicts artifacts | 0 | R6 -5 | 5 | PASS |
| Claims an unrun check passed | 0 | R7 -5 | 5 | PASS |
| Opens outside the supplied directories | 0 | R8 -3 | 3 | PASS |

The script groups R6 and R8 as one unmatched act. Their criteria read different behaviour: a final-message claim and an out-of-scope file open. No two tests read the same observable with the same decisive logic (TS-26). The original compound checks remain a documented TS-13 minor to preserve the H4 separating behaviour. Whole-document checks read different output families; a common upstream adjustment error can fail each without duplicate payment.

## Shares and caps

- Positive P=62: 54/62 (87.1%) whole documents on regenerated hidden extracts, 7/62 (11.3%) isolated controls/provenance/serialization, 1/62 (1.6%) shipped presence and parse.
- 24 tests and 8 judge criteria, below 70 each. The script calls some hidden document checks isolated because their names lack `document`; their bodies re-run a full hidden extract and compare earned output artifacts.
- Test negatives -8, judge negatives -13; each penalty act is at most -5. Judge R1-R4 figure criteria were out of scope for this round.

## Reflex and single wrong readings

See `RECHECK_FIX.md` Trap survival: every file under tests/ except judge.toml, environment/ and solution/solve.py has the same sha256 before and after this round, so the r2 replay numbers stand. The v0 reflex gets 0/62 tests-only. No positive check passes for it. The four centring/angle variants lose 54/62 before and after; first_seen loses 57/62 before and after. Last_occurrence loses 0 before and 10 after, including all three rollup checks.

Judge R5 is now `r5_derive_report_py_uses_named_stage_functions` (conduct, code quality); it shares no observable with any test or other criterion.

STACKING PASS (TS-13 minor retained)

## Lessons for the master

- The stacking script classifies hidden artifact checks by naming heuristics; review the decisive helper before accepting its share and penalty hints.
- When only judge prose changes, an identical raw script output is quick proof that stacking did not move.
