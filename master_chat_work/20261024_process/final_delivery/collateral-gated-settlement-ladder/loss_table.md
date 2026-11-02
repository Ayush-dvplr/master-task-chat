# Loss table: e08c051f-cce9-5aba-b20d-88fb75574b6c (collateral-gated-settlement-ladder), claude-opus-5 run_1

Sources: `run_1/verifier/ctrf.json`, `run_1/verifier/score.json`, `run_1/verifier/reward-details.json` (not synthesized), weights `tests/test_output.py:1087-1108`, `tests/judge.toml`. Reproduced by `tools/loss.py` and by my own docker re-grade (`regrade.txt`).

Score: tests 24/79 = 30.38 %, judge 55/61 = 90.16 % (run used the pre-QC judge, 61 positive), combined 0.5*24/79 + 0.5*55/61 = 0.6027. Under the delivered judge (57 positive, R10/R12 at 3) the same verdicts give 51/57 = 89.47 %, combined 0.5993.

Class key: AMP = AMPLIFICATION of mistake M1 (quoted-integer `amount_minor` accepted, 40 extra events); CONDUCT = judge process criterion (M2). Proof for M1: removing only the coercion branch in a copy of the agent's transform.py gives 79/79 and closing `carry_forward_rate_events` 395 (`regrade.txt`, patch proof).

## Tests (22; positive total 79)

| # | test | weight | kept | lost | result | mistake / class |
|---|---|---|---|---|---|---|
| 1 | artifacts_exist | 1 | 1 | 0 | pass | |
| 2 | output_serialization_is_canonical | 1 | 1 | 0 | pass | |
| 3 | data_quality_lists_every_input_file | 1 | 1 | 0 | pass | |
| 4 | product_summary_lists_every_catalogue_sku | 1 | 1 | 0 | pass | |
| 5 | collateral_gate_blocks_exactly_the_right_events | 5 | 5 | 0 | pass | |
| 6 | normalized_stream_is_exact | 5 | 0 | 5 | fail | M1 AMP (40 extra records) |
| 7 | summary_totals_are_exact | 5 | 0 | 5 | fail | M1 AMP (event_count 10998 vs 10958) |
| 8 | region_rollups_are_exact | 5 | 0 | 5 | fail | M1 AMP |
| 9 | segment_rollups_are_exact | 5 | 0 | 5 | fail | M1 AMP |
| 10 | product_summary_is_exact | 5 | 0 | 5 | fail | M1 AMP |
| 11 | data_quality_ledger_is_exact | 5 | 0 | 5 | fail | M1 AMP (adjustments records 2265 vs 2225, skipped 222 vs 262) |
| 12 | fx_carry_forward_and_predated_currency_are_exact | 5 | 0 | 5 | fail | M1 AMP (per-rule values right; whole-set assert test_output.py:805) |
| 13 | utc_day_shift_and_fiscal_period_are_exact | 5 | 0 | 5 | fail | M1 AMP (whole-map assert :816) |
| 14 | counterparty_dedup_segment_is_exact | 5 | 0 | 5 | fail | M1 AMP (whole-map assert :825) |
| 15 | half_cent_money_rounds_half_up | 5 | 5 | 0 | pass | |
| 16 | orphan_links_use_raw_sales_ids | 5 | 5 | 0 | pass | |
| 17 | corrections_log_overrides_are_applied | 5 | 5 | 0 | pass | |
| 18 | reusable_transform_settles_a_relocated_book | 5 | 0 | 5 | fail | M1 AMP (same bug re-run on relocated copy) |
| 19 | permuted_rows_and_shifted_rates_settle_identically | 5 | 0 | 5 | fail | M1 AMP (same bug on shuffled + rate-scaled copy) |
| 20 | negative_memorized_shipped_book | -5 | - | 0 | not fired | |
| 21 | negative_network_dependency_or_shell_cheat | -3 | - | 0 | not fired | |
| 22 | negative_nondeterministic_output | -3 | - | 0 | not fired | |
| | **total** | **79** | **24** | **55** | 8/22 pass | M1: 55 pts over 11 tests |

## Judge (19 criteria; run weights positive 61, delivered 57)

| id | criterion (short) | target | w run | w delivered | verdict | kept | lost | mistake / class |
|---|---|---|---|---|---|---|---|---|
| R1 | states blocked value -13292764300 | message | 5 | 5 | yes | 5 | 0 | |
| R2 | states 164 blocked counterparties | message | 3 | 3 | yes | 3 | 0 | |
| R3 | states 395 carry-forward events | message | 3 | 3 | NO ("states 397 ... not the required 395") | 0 | 3 | M1 AMP (patched run prints 395) |
| R4 | states 2109 day-shift | message | 3 | 3 | yes | 3 | 0 | |
| R5 | states 710 corrected | message | 3 | 3 | yes | 3 | 0 | |
| R6 | states 680 half-cent | message | 5 | 5 | yes | 5 | 0 | |
| R7 | states 16 underwater | message | 3 | 3 | yes | 3 | 0 | |
| R8 | states 685349 uncatalogued grams | message | 3 | 3 | yes | 3 | 0 | |
| R9 | states 105 stale-link refunds | message | 3 | 3 | yes | 3 | 0 | |
| R10 | interleaves acceptance with running balance | trajectory | 5 | 3 | yes | 5 | 0 | |
| R11 | reads policy constants from policy.ini | trajectory | 3 | 3 | yes | 3 | 0 | |
| R12 | money as one exact decimal expression | trajectory | 5 | 3 | yes | 5 | 0 | |
| R13 | inspects every input file before designing | trajectory | 3 | 3 | yes | 3 | 0 | |
| R14 | runs transform with explicit dirs | trajectory | 5 | 5 | yes | 5 | 0 | |
| R15 | verifies against a reordered second corpus | trajectory | 3 | 3 | NO ("did not create and verify against a second corpus with reordered rows") | 0 | 3 | M2 CONDUCT (unstated) |
| R16 | names where each artifact was written | message | 3 | 3 | yes | 3 | 0 | |
| R17 | repeats one erroring command 3x | trajectory | -3 | -3 | not fired | - | 0 | |
| R18 | closing figure contradicts own run | trajectory | -5 | -5 | not fired | - | 0 | |
| R19 | reviewable code (named helpers, specific exceptions) | trajectory | 3 | 3 | yes | 3 | 0 | |
| | **total** | | **61** | **57** | 15/17 positives | **55** | **6** | M1 3, M2 3 |

## By class (raw points)

| class | test pts | judge pts | combined pts (x 0.5/79 or 0.5/61) |
|---|---|---|---|
| AMPLIFICATION (M1, one stated-rule slip) | 55 | 3 | 0.3481 + 0.0246 = 0.3727 |
| CONDUCT (M2, R15) | 0 | 3 | 0.0246 |
| GENUINE / AMBIGUITY / HIDDEN RULE / JUDGE ERROR / ARTEFACT | 0 | 0 | 0 |

The M1 root is itself a GENUINE trap (stated rule, schema.md:34-35 and :148-149); the 11-test bill is amplification.
