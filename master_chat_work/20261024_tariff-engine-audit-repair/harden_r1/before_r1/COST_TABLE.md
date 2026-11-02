# COST_TABLE (G10), measured

Method: each wrong reading is patched alone into a copy of `solution/solve.py` (WORK/measure_variants.py),
the patched oracle runs on a fresh copy of `environment/ci` and `environment/repo`, then the real
`tests/test_output.py` runs on its `/app/out` (WORK/run_checks.py, rewardkit stub). Test points are out of
121 positive points. Overall = 0.5 x tests + 0.5 x rubric, with rubric 90. Raw results: scratch `g10.json`,
`g10c.json` (copied numbers below). Measured 2026-10-24 20:20-20:34 IST, and every row re-measured
20:38-20:42 IST on the final test file (corpus gained an active meter with only rejected reads; `g10v2.json`):
all scores identical.

| lever | wrong reading injected | tests score | points lost | lever alone loss | all but one right, overall | gate |
|---|---|---|---|---|---|---|
| oracle | none | 121/121 | 0 | 0% | 95.0 | |
| LV-TR-4 | quoted integer coerced (`"37"`, `" 37 "` billed) | 31/121 | 90 | 74.4% | 57.8 | pass |
| LV-TR-3 | month = calendar month of the period start | 46/121 | 75 | 62.0% | 64.0 | pass |
| LV-TR-3 | month = 30 days (shipped code, visible assert A kept true) | 30/121 | 91 | 75.2% | 57.4 | pass |
| LV-TR-2 | line amounts half up (exact decimals) | 46/121 | 75 | 62.0% | 64.0 | pass |
| LV-TR-2 | line amounts from binary floats, `round(x, 2)` | 46/121 | 75 | 62.0% | 64.0 | pass |
| LV-TR-2 partial | credit rounded on its own, total = subtotal - credit | 96/121 | 25 | 20.7% | 84.7 | partial variant, accepted by master (change 2) |
| LV-TR-1 | amplifier: code fixed, both visible asserts kept | 115/121 | 6 | 5.0% | 92.5 | amplifier, not one of the three |

Every gating lever (LV-TR-2, LV-TR-3, LV-TR-4) loses more than 25% of test points alone and every
all-but-one-right row is below 70 overall. LV-TR-1 is recorded as amplifier: its own rows are
`delivered_visible_tests_pass` (3) and `corrected_tests_name_the_changed_tests` (3); bending the code to
the visible asserts (keeping `/30` or the inflated credit base) is the LV-TR-3 `/30` row above.

## One fact wrong (CL-4), measured

One figure off by 0.01 on one hidden account, everything else right.

| lever family | fact made wrong | account (corpus) | tests score | points lost |
|---|---|---|---|---|
| LV-TR-2 energy line | first energy line +0.01 | V2363 (fresh, also in rescaled) | 91/121 | 30 (24.8%) |
| LV-TR-2 energy line | first energy line +0.01 | N0589 (api only) | 106/121 | 15 (12.4%) |
| LV-TR-3 standing line | last standing line +0.01 | N0589 (api only) | 106/121 | 15 (12.4%) |
| LV-TR-4 quantity | one quoted read of one account coerced | N0589 (api only) | 106/121 | 15 (12.4%) |

The fresh corpus is reused, with shuffled rows and one rescaled rate, by the rescaled trio, so an account
of the fresh corpus counts twice; an account that appears in one corpus costs one trio (15 points).

## Negatives (TS-16)

`negative_hardcoded_sample_answers` and `negative_visible_test_removed` stay unfired for the oracle
and for all seven wrong-reading rows above and the one-fact rows. The cheat row `C_hardcode_shipped`
(package copies the shipped invoices for any account id it has seen) fires
`negative_hardcoded_sample_answers` and scores 81/121 before the penalty.
