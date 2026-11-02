# STACKING_CHECK: sentinel-policy-recompute (harden round 3, 9aaa7c6)

Tool: `master_chat_tasks/tools/stacking_check.py` (raw output `stacking_check_raw.txt`). Rows confirmed by reading `tests/test_output.py` and by local scoring (`WORK/local_score.py`, rewardkit 0.2.1; oracle 52/52 = 1.000). Tests channel only.

Levers: N4 timeout pool (the only counted lever this round, master decision 25 Oct), N1 region allowance, N2 timeout unit by version cutover, N3 window admit count with draw_order (feeders kept from round 2), L7 per-term rounding (noise), L1 recomputed controls (amplifier). "carried" = repair faults kept from earlier rounds. Reflex column = the probe-2 agent program (`OUT/agent_program/out/tool.zip`) scored locally, 36/52.

## (a) Per-test rows

| id | w | observable | decisive logic | misreads that fail it | reflex |
|---|---|---|---|---|---|
| hidden_region_allowance_hard | 5 | policy_resolved.json + graded trace on n1-a, n1-b | r-north drawn by t-aurora; r-03 rows do not draw r-north | N1 (off, per tenant, one counter) | PASS |
| hidden_unit_cutover_hard | 5 | same documents on n2-a, n2-b | unit from version effective_from vs cutover | N2 (raw, from rev) | PASS |
| hidden_window_admit_hard | 5 | same documents on n3-a, n3-b | WIN-AUTH / WIN-AUX admit counts across tenants | N3 (off, resolved tenant only) | PASS |
| hidden_timeout_pool_hard | 5 | same documents on pool-a, pool-b | WIN-AUTH timeout_pool binds; a row falls below 100, whole pool shared again across the rest | N4 (off, fits re-checked, no re-share, only dropped ms, no drop, resolved key only) | FAIL (pool-a 2747 vs 2771) |
| hidden_policy_resolved_document_matches | 5 | policy_resolved.json on hidden-a..d (coupling) | applied set from both counters, unit, pool share (hidden-c drop, hidden-d binding pool) | N1, N2, N3, N4, draw_order, carried | FAIL (hidden-c 2610 vs 2565) |
| hidden_threshold_curve_document_matches | 5 | threshold_curve.json on hidden-a..d | per-term contribution of the applied set | N1, N3, draw_order, L7, carried | PASS |
| hidden_dependency_trace_document_matches | 5 | dependency_trace.json graded keys on hidden-a..d | applied_overrides, ledger_controls with cutover unit, resolution_order | N1, N2, N3, draw_order, L1, carried | PASS |
| cli_init_and_set_rebuild_config_from_authoritative_values | 3 | config.json rebuilt by delivered init/set from reference values | coercion, canonical write | carried (set/write_json) | PASS |
| mutation_risk_delta_moves_only_contribution | 3 | curve + policy on hidden-c base (pool 1000) with OV-K042-c6 risk 4 | contribution 67, policy unchanged at 2565 | L7, N3, N4, first-only | FAIL (2610 vs 2565) |
| mutation_allowance_cut_drops_later_override | 3 | policy on hidden-a base with r-north 1 | t-aurora row takes the only r-north unit | N1 (off, per tenant) | PASS |
| mutation_pool_cut_reshares_timeout | 3 | policy on pool-b base with WIN-AUTH pool 900 | drop then whole-pool re-share, 2899 | N4 (every reading) | FAIL (2872 vs 2899) |
| validate_accepts_supplied_config_and_rejects_missing_key | 3 | rc/stdout of delivered validate | required_keys split | carried validate | PASS |
| hidden_resolve_rerun_is_canonical_and_byte_identical | 1 | bytes of two resolve runs on hidden-a | canonical, deterministic, differs from shipped policy | constant resolve | PASS |
| shipped_artifacts_carry_policy_runs_and_archive | 1 | seven delivered artifacts | shipped values, transcript, controls incl t-aurora, archive | stale corpus reading | PASS |
| negative_hardcoded_sample_answers | -5 | AST literals in delivered cli.py/schema | hardcoding | none | not fired |
| negative_transcript_disagrees_with_config | -3 | last recorded set vs config.json | forged transcript | none | not fired |
| negative_url_or_secret_in_artifacts | -3 | `://`, api_key, password in artifacts | host/credential material | none | not fired |

TS-26: the tool groups the four `_hard` tests (same documents, same helper). Not duplicates: each reads its own corpora (n1-*, n2-*, n3-*, pool-*), and single_lever.py shows each fails only under its own lever (N1 readings fail region_hard and no other `_hard`; N2 only cutover_hard; N3 only admit_hard; N4 only timeout_pool_hard). The coupling checks read hidden-a..d, which none of the `_hard` tests read. TS-13: the trace check's 5 asserts all grade one document.

PL note: N4 fails four checks (16/52) through one upstream rule. They read different observables on different corpora (pool-a/b documents, hidden-c policy, a one-value risk mutation of hidden-c, a one-value pool mutation of pool-b); the two mutations isolate a single changed value each. The round keeps one counted lever (N4) with N1-N3 as feeders: this breaks the >= 3 independent levers rule (G10/LEVER_RULES), accepted by the master on 25 Oct for this last round.

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

The tool's UNMATCHED row (17) lumps five distinct acts; split by hand above, every group <= 5. Negatives unchanged from round 2. No negative grades a lever reading.

## (c) Shares and caps

P = 52 (weights 5/3/1 only). Hidden or mutated reruns 48/52 = 92.3% (>= 30%); `_hard` families 20 (38.5%); coupling whole-document 15 (28.8%); isolated 3 + rebuild 3 (11.5%); mutation 9 (17.3%); shipped-only 1 (1.9%). Tests 17, criteria 16 (judge batched, P 40). Weight-1: rerun and merged shipped check only (not core). Judge J2 conduct R12 (N2), R13 (N1), R14 (N3), R15, R16 (N4, new, w3); J3 R9; J4 R10.

## (d) Cost table (G10), from WORK/COST_TABLE.md

Overall = 0.5 x tests + 0.5 x judge; judge at the probe-2 measure 14/40 = 35.0 (R16 assumed 0).

| lever (one fact wrong) | tests | share lost | overall at judge 35.0 | at rubric 90 (info) | gate |
|---|---|---|---|---|---|
| N4 timeout pool (each of six readings) | 36/52 | 30.8% | 52.1 | 79.6 | PASS (counted) |
| N1 per-tenant allowance (feeder) | 29/52 | 44.2% | 45.4 | 72.9 | PASS |
| N1 one counter for every row (feeder) | 32/52 | 38.5% | 48.3 | 75.8 | PASS |
| N2 unit from rev (feeder) | 37/52 | 28.8% | 53.1 | 80.6 | PASS |
| N3 admits ignored / resolved tenant only (feeder) | 29/52 | 44.2% | 45.4 | 72.9 | PASS |
| draw_order (either direction) | 37/52 | 28.8% | 53.1 | 80.6 | PASS |
| L7 summed rounding (noise) | 44/52 | 15.4% | 59.8 | 87.3 | info |
| L1 trusted controls (amplifier) | 47/52 | 9.6% | 62.7 | 90.2 | info |

Differential fuzz (OUT/fuzz, OUT/proto): N1-N3, L7, L1 0/307 corpora differ on the probe-2 agent program; N4 differs on 111/300 (37%). Only N4 counts as a lever under the master's rule.

Reflex / agent program: probe-2 agent program 36/52 = 0.6923 (above the 0.20 reflex gate; the master's round-3 target is tests 85-95 for one genuine miss, so the lever was not strengthened further; reported, not hidden).

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 24 mutants (m1-m24, N4 m19-m24), every rule has a mutant failing at least one test; 0 uncovered.

STACKING PASS (with the master-accepted single counted lever and the reflex-gate exception noted above)
