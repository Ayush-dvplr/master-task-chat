# STACKING_CHECK sentinel-policy-recompute (P12 r2, 47d0997)

Source: `stacking_check.py` run on the fixed BUNDLE (raw output in `stacking_check_raw.txt`), read against the code. Tests: 12 checks, positive 31, negatives -11. Judge: 15 criteria, positive 34, negative 17, batched.

## (a) Test to observable map

| test | w | class | observable |
|---|---|---|---|
| hidden_policy_resolved_document_matches | 5 | whole_doc | policy_resolved.json on hidden-a/b/c vs reference |
| hidden_threshold_curve_document_matches | 5 | whole_doc | threshold_curve.json on hidden-a/b/c vs reference |
| hidden_dependency_trace_document_matches | 5 | whole_doc | dependency_trace.json (key set, resolution_order relative order of the four chain files, then graded keys) on hidden-a/b/c |
| hidden_config_document_rebuilt_by_cli_matches | 5 | whole_doc | delivered init/set rebuild of config.json on hidden-a/b/c |
| mutation_risk_delta_moves_only_contribution | 3 | mutation | threshold_curve + policy_resolved on mutation-risk |
| mutation_allowance_cut_drops_later_override | 3 | mutation | policy_resolved on mutation-allowance |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 | isolated | validate exit codes on good.json / bad.json |
| hidden_resolve_rerun_is_canonical_and_byte_identical | 1 | format_hidden | two resolve runs on one hidden-a corpus dir: byte identity and canonical form, and the written policy differs from the shipped policy (no reference equality since r2) |
| shipped_artifacts_follow_field_specs | 1 | shipped_only | the seven shipped artifacts (merged; KEEP M1/M2, see QC_DEFENCE TS-13/TS-26) |
| negative_hardcoded_sample_answers | -5 | negative | 285 / 2250 literals in cli.py or schema.json |
| negative_transcript_disagrees_with_config | -3 | negative | report.json transcript values vs config.json |
| negative_url_or_secret_in_artifacts | -3 | negative | URL or secret strings in artifacts |

TS-26 duplicates: none. The rerun check no longer reads the reference, so it shares no decisive logic with the four whole-document checks. TS-13 hint: shipped_artifacts_follow_field_specs (22 asserts), kept (M1/M2).

## (b) AL-28 penalty groups by act (named by hand; the script lumped six unmatched acts)

| act | tests | judge | sum abs | verdict |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | - | 3 | PASS |
| leaking a URL or secret into artifacts | negative_url_or_secret_in_artifacts -3 | - | 3 | PASS |
| editing the input data under /app/data | - | R3 -3 | 3 | PASS |
| writing an undeclared file under /app/out | - | R4 -3 | 3 | PASS |
| passing `set` a config value the repaired resolve did not print | - | R8 -5 | 5 | PASS |
| claiming a check passed that its output contradicts | - | R9 -5 | 5 | PASS |
| an except clause in the repaired cli.py that discards an error and continues | - | R10 -1 | 1 | PASS |

## (c) Shares of positive test weight (31)

- whole_doc 20 (64.5%) >= 50% PASS
- isolated 3 + mutation 6 = 9 (29.0%) <= 30% PASS
- format_hidden 1 (3.2%)
- shipped_only 1 (3.2%) <= 5% PASS
- caps: tests 12, criteria 15 (<= 70) PASS

## (d) Reflex and single-lever variants (fixed tests, local_score.py)

| program | earned / 31 | score | loss share |
|---|---|---|---|
| oracle | 31 | 1.0000 | 0 |
| nop | 0 | 0.0000 | 1.000 |
| stub (seven empty artifacts) | 0 | 0.0000 | 1.000 |
| reflex (harden_r1 agent program, build replay) | 5 | 0.1613 | 0.839 |
| first-only | 11 | 0.3548 | 0.645 |
| no allowance | 8 | 0.2581 | 0.742 |
| allowance per principal | 8 | 0.2581 | 0.742 |
| raw timeout | 16 | 0.5161 | 0.484 |
| abs(v) < 100 heuristic | 16 | 0.5161 | 0.484 |
| sum rounding | 23 | 0.7419 | 0.258 |
| controls never recomputed | 26 | 0.8387 | 0.161 |
| window-version only (new, r2) | 11 | 0.3548 | 0.645 |
| inclusive window end | 4 | 0.1290 | 0.871 |

Reflex 0.1613 <= 0.20 (before 0.1290; +0.032, within +0.05). Trap survival on sum rounding is 0.889 (< 0.90), reported in RECHECK_FIX.md; that is a trap verdict, not a stacking one.

STACKING PASS
