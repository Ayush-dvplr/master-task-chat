# STACKING_CHECK: sentinel-policy-recompute (harden round 2, 0074a64)

Tool: `master_chat_tasks/tools/stacking_check.py` (raw output `stacking_check_raw.txt`). Rows confirmed by reading `tests/test_output.py` and by local scoring (`WORK/local_score.py`, rewardkit 0.2.1; oracle 44/44 = 1.000). Tests channel only.

Levers: N1 region override allowance, N2 timeout unit by version cutover, N3 window admit count (with draw_order), L7 per-term rounding (graded noise), L1 recomputed controls (N2 amplifier). "carried" = repair faults kept from earlier rounds (half-open end, version gate, B9, client version, seconds base, tier, convergence, validate split, write_json).

## (a) Per-test rows

| id | w | observable | decisive logic | misreads that fail it | reflex |
|---|---|---|---|---|---|
| hidden_region_allowance_hard | 5 | policy_resolved.json + graded trace (no controls) on n1-a, n1-b | r-north drawn by t-aurora; r-03 rows do not draw r-north | N1 (off, per tenant, one counter) | FAIL |
| hidden_unit_cutover_hard | 5 | same documents on n2-a, n2-b | unit from version effective_from vs cutover | N2 (raw, from rev) | FAIL |
| hidden_window_admit_hard | 5 | same documents on n3-a, n3-b | WIN-AUTH / WIN-AUX admit counts across tenants | N3 (off, resolved tenant only) | FAIL |
| hidden_policy_resolved_document_matches | 5 | policy_resolved.json on hidden-a..d (coupling) | applied set from both counters, timeout unit | N1, N2, N3, draw_order both ways, carried | FAIL |
| hidden_threshold_curve_document_matches | 5 | threshold_curve.json on hidden-a..d | per-term contribution of the applied set | N1, N3, draw_order, L7, carried | FAIL |
| hidden_dependency_trace_document_matches | 5 | dependency_trace.json graded keys on hidden-a..d | applied_overrides, ledger_controls with cutover unit, resolution_order | N1, N2, N3, draw_order, L1, carried | FAIL |
| cli_init_and_set_rebuild_config_from_authoritative_values | 3 | config.json rebuilt by delivered init/set from reference values | coercion, canonical write | carried (set/write_json) | PASS |
| mutation_risk_delta_moves_only_contribution | 3 | curve + policy on hidden-c base with OV-K042-c6 risk 4 | contribution 67, policy unchanged | L7, N3, first-only | FAIL |
| mutation_allowance_cut_drops_later_override | 3 | policy on hidden-a base with r-north 1 | t-aurora row takes the only r-north unit | N1 (off, per tenant) | FAIL |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 | rc/stdout of delivered validate | required_keys split | carried validate | PASS |
| hidden_resolve_rerun_is_canonical_and_byte_identical | 1 | bytes of two resolve runs on hidden-a | canonical, deterministic, differs from shipped policy | constant resolve | PASS |
| shipped_artifacts_carry_policy_runs_and_archive | 1 | seven delivered artifacts | shipped values, transcript, controls incl t-aurora, archive | stale corpus reading | FAIL |
| negative_hardcoded_sample_answers | -5 | AST literals in delivered cli.py/schema | hardcoding | none | not fired |
| negative_transcript_disagrees_with_config | -3 | last recorded set vs config.json | forged transcript | none | not fired |
| negative_url_or_secret_in_artifacts | -3 | `://`, api_key, password in artifacts | host/credential material | none | not fired |

TS-26: the tool groups the three `_hard` tests (same documents, same helper). Not duplicates: each reads its own corpora (n1-*, n2-*, n3-*), and single_lever.py shows each fails only under its own lever (N1 readings fail region_hard and no other `_hard`; N2 only cutover_hard; N3 only admit_hard). The coupling checks read hidden-a..d, which none of the `_hard` tests read. TS-13: the trace check's 5 asserts all grade one document.

## (b) Penalty groups by act (tests + judge)

| act | members | sum abs w | verdict |
|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | 5 | PASS |
| forging the command transcript | negative_transcript_disagrees_with_config -3 | 3 | PASS |
| host or credential material in artifacts | negative_url_or_secret_in_artifacts -3 | 3 | PASS |
| config from a resolve on a copied, edited corpus | judge R3 -3 | 3 | PASS |
| undeclared file under /app/out | judge R4 -3 | 3 | PASS |
| set value no repaired resolve printed | judge R8 -5 | 5 | PASS |
| false check claim | judge R9 -5 | 5 | PASS |

The tool's UNMATCHED row (17) lumps five distinct acts; split by hand above, every group <= 5. No negative grades a lever reading.

## (c) Shares and caps

P = 44 (weights 5/3/1 only). Hidden or mutated reruns 40/44 = 90.9% (>= 30%); `_hard` families 15 (34.1%); coupling whole-document 15 (34.1%); isolated 3 + rebuild 3 (13.6%); mutation 6 (13.6%); shipped-only 1 (2.3%, <= 5% per master ruling 5). Tests 15, criteria 15 (judge batched, P 37). Weight-1: rerun and merged shipped check only (not core). Judge J2 conduct R12 (N2), R13 (N1), R14 (N3), R15; J3 R9; J4 R10.

## (d) Cost table (G10), from WORK/COST_TABLE.md

| lever (one fact wrong) | tests | share lost | overall at judge 51.35 | at rubric 90 (info) | gate |
|---|---|---|---|---|---|
| N1 per-tenant allowance | 21/44 | 52.3% | 49.5 | 68.9 | PASS |
| N1 one counter for every row | 24/44 | 45.5% | 52.9 | 72.3 | PASS |
| N2 unit from rev | 29/44 | 34.1% | 58.6 | 78.0 | PASS |
| N3 admits ignored / resolved tenant only | 21/44 | 52.3% | 49.5 | 68.9 | PASS |
| draw_order (either direction) | 29/44 | 34.1% | 58.6 | 78.0 | PASS |
| L7 summed rounding (noise) | 36/44 | 18.2% | 66.6 | 85.9 | info |
| L1 trusted controls (amplifier) | 39/44 | 11.4% | 70.0 | 89.3 | info |

Each counted lever alone >= 25%; all-but-one overall < 70 at the measured judge (16/37 + 3 for R11 = 19/37).

Reflex (probe-1 program, region key adapted): 0.1591 delivered, 0.1818 rebuilt, 0.1364 unadapted (<= 0.20 PASS).

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 16 rules, 21 mutants (WORK/trap/after_h2_mutants.txt), every rule has a mutant failing at least one test; 0 uncovered.

STACKING PASS
