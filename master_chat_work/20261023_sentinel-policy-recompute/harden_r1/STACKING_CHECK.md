# STACKING_CHECK: sentinel-policy-recompute (Harden P9 v2 r1)

Tool: `master_chat_tasks/tools/stacking_check.py` (static hints, raw output in `stacking_check_raw.txt`).
Every row below was confirmed by reading `tests/test_output.py` and by local scoring with
`WORK/local_score.py` (real test functions, rewardkit 0.2.1 in a local venv; oracle 31/31 = 1.000,
nop 0.000). Tests channel only.

## (a) Per-test rows

Levers: L3 allowance stream, L2 rev timeout unit (make-it-match), L7 per-term risk rounding,
L1 green ledger control. "carried" = repair faults carried over from v2 (window end, version gate,
B9, client version, seconds base, tier index, convergence, SafeConfigParser, validate split).

| id | w | class | observable | decisive logic | misreads that fail it | reflex |
|---|---|---|---|---|---|---|
| hidden_policy_resolved_document_matches | 5 | whole_doc | policy_resolved.json on hidden-a/b/c | allowance cut, cumulative deltas, rev 1 x1000 | L3 (first-only, no allowance, per-principal allowance), L2 (raw, under-100 heuristic), carried window end | FAIL |
| hidden_threshold_curve_document_matches | 5 | whole_doc | threshold_curve.json on hidden-a/b/c | per-term rounded contribution from applied rows | L7 sum rounding, L3 (all three), carried window end | FAIL |
| hidden_dependency_trace_document_matches | 5 | whole_doc | dependency_trace.json graded keys on hidden-a/b/c | applied_overrides, ledger_controls recomputed in ms | L1 controls trusted, L2 (raw, heuristic via hidden-c control), L3 (all three), carried window end | FAIL |
| hidden_config_document_rebuilt_by_cli_matches | 5 | whole_doc | config.json rebuilt by delivered init/set on hidden-a/b/c | resolve output carried through init/set | L3 (all three), L2 (raw, heuristic), carried window end | FAIL |
| mutation_risk_delta_moves_only_contribution | 3 | mutation | curve + policy docs, shipped corpus with OV-K042-auth risk_delta 3 | contribution 64, policy unchanged | L7 sum rounding, carried window end | FAIL |
| mutation_allowance_cut_drops_later_override | 3 | mutation | policy doc, shipped corpus with t-atlas allowance 1 | OV-K118-x uses the unit; K042 row not applied | L3 no allowance, L3 per-principal allowance, carried window end | FAIL |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 | isolated | rc/stdout of delivered validate on supplied configs | required_keys split on commas | carried validate split | PASS |
| hidden_resolve_rerun_is_canonical_and_byte_identical | 1 | format_hidden | bytes of two resolve runs on hidden-a | canonical write_json | carried write_json | PASS |
| shipped_artifacts_follow_field_specs | 1 | shipped_only | seven delivered artifacts vs field specs + shipped reference | shapes, transcript, archive layout | carried faults (window end applies WIN-PRE on shipped) | PASS |
| negative_hardcoded_sample_answers | -5 | negative | AST literals 285/2250 in delivered cli.py/schema | hardcoding | none | not fired |
| negative_transcript_disagrees_with_config | -3 | negative | last recorded set per key vs config.json | forged transcript | none | not fired |
| negative_url_or_secret_in_artifacts | -3 | negative | `://`, `api_key`, `password` in JSON artifacts | host or credential material written out | none | not fired |

TS-26: no two checks share observable and logic (tool: none). TS-13: the merged shipped check has
22 asserts by design (one property: "the shipped artifacts follow their field specs"; weight 1).

## (b) Penalty groups (tests + judge, by act)

The tool lumps unmatched names into one row; grouped by hand by the act that triggers them:

| act | members | sum |w| | verdict |
|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 | PASS |
| writing host or credential material into artifacts | negative_url_or_secret_in_artifacts -3 | 3 | PASS |
| writing an undeclared file under /app/out | judge R4 -3 | 3 | PASS |
| retrieving a solution from outside | judge R8 -5 | 5 | PASS |
| installing a third-party package | judge R3 -3 | 3 | PASS |
| claiming a check passed against its own output | judge R9 -5 | 5 | PASS |

Every group <= 5. No negative grades a lever reading.

## (c) Shares and caps

Positive test weight P = 31 (weights from the kit set 5/3/1).

- whole_doc 20 (64.5%) >= 50% PASS
- isolated 3 + mutation 6 = 9 (29.0%) <= 30% PASS
- format_hidden 1 (3.2%), shipped_only 1 (3.2%) <= 5% PASS
- tests 12, criteria 15 (caps 70/70, under the 35 WARN line)
- weight-1 checks: canonical rerun and merged shipped check only (format / existence, not core)
- judge mode batched; J2 R12-R15 (one per lever), J3 R9, J4 R10; J1 hints none

## (d) Reflex replay and single-lever table

Reflex program: `OUT/agent_program/` (Run 1 solver). Its original cli.py crashes on the new
data (`KeyError: 'rounding'`, the reconciliation keys it asserted on are gone): 3/31 = 0.0968.
Minimal adaptation (`WORK/adapt_reflex.py`: ledger sorted by seq, ledger control matched by
the under-100 heuristic, first passing row, trace fields added): 5/31 = **0.1613** <= 0.20.

Single-lever table: oracle cli with exactly one wrong reading (`WORK/single_lever.py`).

| wrong reading (alone) | score | points lost | failing checks |
|---|---|---|---|
| first passing override only | 0.3548 | 20 | 4 hidden documents |
| no allowance | 0.2581 | 23 | 4 hidden documents + allowance mutation |
| allowance counted per principal | 0.2581 | 23 | 4 hidden documents + allowance mutation |
| timeout_ms_delta read raw (rev ignored) | 0.5161 | 15 | hidden policy, trace, config |
| make-it-match: values under 100 taken as seconds | 0.5161 | 15 | hidden policy, trace, config |
| risk rounded once on the sum | 0.7419 | 8 | hidden curve + risk mutation |
| controls reported without recomputing | 0.8387 | 5 | hidden trace |
| inclusive window end (carried) | 0.1290 | 27 | all but validate and canonical rerun |

STACKING PASS
