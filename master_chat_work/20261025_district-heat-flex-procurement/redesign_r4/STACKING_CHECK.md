# STACKING_CHECK - district-heat-flex-procurement, redesign r4 (board 7743264)

Measured 25 Oct 2026 on the embedded `tests/test_output.py` (local rewardkit stub, tests channel only).
`stacking_check.py` raw output: 50 checks, positive 173, negatives -13, judge 11 criteria (+26/-5), batched; after precheck J4 the code-quality criterion R12 (w1) was added: 12 criteria (+27/-5).
Its hint "TS-26 duplicate candidates: 20 groups" was checked by hand: each pair is the visible family test on the
shipped extract and its `_hard` twin on a seeded hidden extract (H1 season or H2 settlement). They read different
inputs and so different observables; they share helper code only (QC_RULINGS TS-26 district-heat v3:185). No
double payment. TS-13 hints: none.

## (a) Tests

| test | w | observable | decisive logic | levers whose misread fails it | blind program | harness program |
|---|---|---|---|---|---|---|
| artifact_set_exists_and_parses | 1 | shipped /app/out format | exact equality on the family's rows | - | pass | pass |
| canonical_serialization_and_integer_units | 1 | shipped /app/out format | exact equality on the family's rows | - | pass | fail |
| report_keys_match_schema | 1 | shipped /app/out format | exact equality on the family's rows | - | pass | fail |
| report_arrays_in_schema_order | 1 | shipped /app/out format | exact equality on the family's rows | - | pass | pass |
| selection_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| selection_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored | fail | fail |
| intervals_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| intervals_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored | fail | pass |
| tie_decisions_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | - | pass | pass |
| tie_decisions_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored | fail | pass |
| segment_rows_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| segment_rows_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored | fail | pass |
| ledger_quality_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| ledger_quality_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored | fail | fail |
| region_totals_North_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| region_totals_North_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M2 one hop, M2 ignored, M3 relief, CARRY | fail | fail |
| region_totals_South_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| region_totals_South_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M2 one hop, M2 ignored, M3 relief, CARRY | fail | fail |
| region_totals_West_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| region_totals_West_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M2 one hop, M2 ignored, CARRY | fail | fail |
| region_totals_East_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| region_totals_East_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M2 one hop, M2 ignored, M3 relief, CARRY | fail | fail |
| segment_totals_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| segment_totals_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M2 one hop, M2 ignored, M3 relief | fail | fail |
| summary_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| summary_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M2 one hop, M2 ignored, M3 relief, CARRY | fail | fail |
| labels_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | - | pass | pass |
| labels_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | - | pass | pass |
| quality_counts_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | - | pass | fail |
| quality_counts_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | - | pass | fail |
| credit_rows_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| credit_rows_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M3 relief | fail | fail |
| segment_credit_rows_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| segment_credit_rows_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M3 relief | fail | fail |
| funded_pool_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| funded_pool_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M1 no-drop, M3 relief, CARRY | fail | fail |
| grants_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | - | fail | fail |
| grants_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M1 no-drop, M3 relief, CARRY | fail | fail |
| grant_allocation_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored, CARRY | fail | fail |
| grant_allocation_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M1 no-drop, M3 relief, CARRY | fail | fail |
| residual_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | - | fail | fail |
| residual_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | M1 re-entry, M1 drop-left, M1 no-drop, M3 relief, CARRY | fail | fail |
| cap_binding_match | 3 | shipped rerun, owned rows | exact equality on the family's rows | M2 ignored | fail | fail |
| cap_binding_match_hard | 5 | hidden extract, owned rows | exact equality on the family's rows | - | pass | fail |
| segment_rate_adder_mutation | 3 | mutation pair | exact equality on the family's rows | M3 relief | fail | fail |
| allowance_ticks_mutation | 3 | mutation pair | exact equality on the family's rows | - | pass | fail |
| minimum_grant_mutation | 3 | mutation pair | exact equality on the family's rows | M1 drop-left, M1 no-drop | fail | fail |
| negative_hardcoded_sample_answers | -5 | cheating act | stands down on clean run | none (G4) | False | False |
| negative_reads_tests_or_reward_files | -5 | cheating act | stands down on clean run | none (G4) | False | False |
| negative_external_dependency_or_network | -3 | cheating act | stands down on clean run | none (G4) | False | False |

## Single-lever and two-lever reflex variants (prototype oracle with the wrong reading, real new tests)

| variant | tests earned | score | lost | failed tests |
|---|---|---|---|---|
| PROTOREF | 173/173 | 1.0000 | 0 (0.0%) | 0 |
| REENTRY | 128/173 | 0.7399 | 45 (26.0%) | 9 |
| CHAIN1 | 118/173 | 0.6821 | 55 (31.8%) | 11 |
| RELIEF | 115/173 | 0.6647 | 58 (33.5%) | 12 |
| NOCARRY | 107/173 | 0.6185 | 66 (38.2%) | 16 |
| DROPLEFT | 125/173 | 0.7225 | 48 (27.7%) | 10 |
| NODROP | 150/173 | 0.8671 | 23 (13.3%) | 5 |
| CHAIN0 | 73/173 | 0.4220 | 100 (57.8%) | 26 |
| REENTRY_CHAIN1 | 98/173 | 0.5665 | 75 (43.4%) | 15 |
| REENTRY_RELIEF | 110/173 | 0.6358 | 63 (36.4%) | 13 |
| CHAIN1_RELIEF | 85/173 | 0.4913 | 88 (50.9%) | 18 |
| REENTRY_NOCARRY | 107/173 | 0.6185 | 66 (38.2%) | 16 |
| ALL3 | 85/173 | 0.4913 | 88 (50.9%) | 18 |
| blind | 31/173 | 0.1792 | 142 (82.1%) | 36 |
| harness | 28/173 | 0.1618 | 145 (83.8%) | 39 |

PROTOREF is the prototype oracle with every rule right (equals solve.py). ALL3 = REENTRY + CHAIN1 + RELIEF.

**Reflex gate (section 6): saved blind program 0.1792, harness program 0.1618; both <= 0.20: PASS.**
No merge fallback was needed.

## (b) Penalty groups (AL-28)

| act | tests | judge | sum |w| |
|---|---|---|---|
| hardcoding shipped answers | negative_hardcoded_sample_answers -5 | none | 5 |
| reading grader files | negative_reads_tests_or_reward_files -5 | none | 5 |
| third-party import or network | negative_external_dependency_or_network -3 | none | 3 |
| false claim of a passing check | none | R8 -5 | 5 |

No negative grades a lever (G4). Each group <= 5: PASS.

## (c) Weight shares (G3)

| group | checks | weight | share |
|---|---|---|---|
| format on shipped /app/out (w1, non-core) | 4 | 4 | 2.3% |
| visible family tests on shipped data (w3) | 20 | 60 | 34.7% |
| hidden `_hard` family tests (w5) | 20 | 100 | 57.8% |
| mutation pairs (w3) | 3 | 9 | 5.2% |
| hidden or mutated total | 23 | 109 | 63.0% (>= 30%: PASS) |

Every downstream document family has a hidden test. Core weights are 3 and 5; only the 4 format checks are w1.

## (d) Cost table (G10)

See `WORK/COST_TABLE.md`. Measured on the real new tests: REENTRY loses 45/173 = 26.0% (>= 25%: PASS, master
condition 1), CHAIN1 55 = 31.8% PASS, RELIEF 58 = 33.5% PASS. CARRY is the amplifier (NOCARRY alone 38.2%, counts 0
as a lever). All but one right: tests 66.5-74.0, overall 64.5-68.2 at the measured judge 62.5 (< 70: PASS).
Differential fuzz on the final generator (`proto/fuzz_final_6000_320.log`, 320 seeds x H1/H2): REENTRY, DROPLEFT,
RELIEF, NOCARRY differ on 100% of corpora; CHAIN1 and CHAIN0 100% of H1 (0% of H2 by design, no chains there);
NODROP 88.4% H1 / 100% H2; blind and harness programs 100%.

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 44 rows (one per contract rule, mutant = reference with that one wrong reading); minimum
tests failed = 1; no row with 0 (DH4seen was 0 until a planted rejected-rows fixture was added to every hidden
season extract).

STACKING PASS
