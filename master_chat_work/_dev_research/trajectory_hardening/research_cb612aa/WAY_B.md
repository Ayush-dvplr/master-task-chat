# Way B: tune the bundle, then one new run (cb612aa)

Sources: every run under `H/jobs/<slug>/trajectory/claude-opus-5/Run 1` and `H/jobs/_archive/*/…/Run 1`, grouped by `result.json` `task_checksum`, with scores from `pass_summary.json` (tests / rubric / final). Cross-checked with `master_chat_tasks/registry/scores.jsonl` lines 54-94. Archive folder suffixes are archive times, not run times, so runs are ordered by `started_at`.

## 1. Run variance on unchanged bundles (same checksum, two runs)
| task | checksum | run A | run B | Δtests | Δfinal |
|---|---|---|---|---|---|
| sentinel | 2e46383072 | 96.18 / 35.0 / 65.59 (27T00:23) | 78.63 / 12.5 / 45.56 (27T00:49) | **17.55** | **20.03** |
| caldermoor | 895747c64a | 98.45 / 0 / 49.23 (26T15:28, R12 -3 fired) | 94.33 / 8.57 / 51.45 (26T16:02) | 4.12 | 2.22 |
| (ruling) | LEVER_RULES_v3.md:145 G13 | tests 37.93 | tests 17.12 | 20.81 | — |

match-replay b528194f26 also has two runs, but the first has an empty pass_summary, so it is unusable.
**Use ±18-21 pp tests and ±20 pp final for one run**, which matches G13's "±20 tests / ±10 final" on tests and is twice as wide on final.

## 2. Before/after pairs (consecutive bundle versions, one run each)
| task | before -> after (final; tests in brackets) | Δfinal | gate after (tests<100 and final<70) |
|---|---|---|---|
| caldermoor | 87.22 (74.44) -> 73.69 (100) -> 52.27 (100) -> 56.82 (100) -> 73.22 (98.45) -> 49.23 / 51.45 (98.45 / 94.33) | -13.5, -21.4, +4.6, +16.4, -22.9 | met only on the last |
| cohort-retention | 58.67 (42.35) -> 100 (100) | +41.3 | no (fix round, not a harden round) |
| data-product | 94.65 (100) -> 100 (100) | +5.4 | no |
| dispatch | 64.19 (29.67) -> 76.52 (67.33) -> 14.7 (35.64) | +12.3, -61.8 | met |
| district-heat | 100 -> 81.25 -> 68.52 (tests 100 throughout) | -18.8, -12.7 | **no**: tests 100 |
| emberforge | 84 (68) -> 43.07 (1.94) -> 27.31 (29.63) -> 59.91 (94.83) | -40.9, -15.8, +32.6 | met |
| match-replay | 80.43 (63.19) -> 43.42 (69.19) | -37.0 | met |
| metered-usage | 87.5 -> 85.3 -> 82.35 (tests 100 throughout) | -2.2, -3.0 | **no**: tests 100 |
| schema-migration | 84.44 (99.3) -> 46.16 (100) | -38.3 | **no**: tests 100 |
| sensor-network | 71.16 -> 90 -> 87.5 (tests 100) | +18.8, -2.5 | no |
| sentinel | 77.78 -> 71.62 -> 68.92 -> 70.0 (tests 100) -> 65.59 / 45.56 (96.18 / 78.63) -> 50.1 (80.69) | -6.2, -2.7, +1.1, -4.4 / -24.4, +4.5 vs the mean | met from round 5 (the ledger_repair lever) |
| tariff | 81.25 -> 51.66 -> 59.09 (tests 100) | -29.6, +7.4 | **no**: tests 100 |
| vendor-archive | 52.41 (4.83) -> 100 -> 71.88 (100) | +47.6, -28.1 | no |

## 3. What the pairs show
- 29 rounds in total. Final went down in 19 and **up in 10**. Several rises came from hardening rounds: caldermoor r3-r4, sentinel r3, tariff r2, emberforge r3. A single after-run cannot tell a lever from noise when |Δ| < 20.
- Rounds that started at tests 100: 17. Rounds that ended below 100 from there: **2** (caldermoor r4 98.45; sentinel r4, after the ledger_repair data lever, harden_t3 DIAGNOSIS.md:32-49). Every judge-only or wording round left tests at 100, which agrees with QL `LEVER_RULES_v3.md:207` and Q5 `QC_RULINGS.md:145`.
- Judge rounds move rubric reliably downward (sentinel 55.6 -> 19.5, tariff 62.5 -> 3.3, schema 69.6 -> -7.7). That moves final, but the push gate also needs tests < 100. So for the 6 pipeline tasks the binding constraint is **one lost positive test on a fresh run**. That requires a test lever (P-3 hidden scale / exact optimum), not a judge lever.

## 4. Reliability of "one new run" for push
- After a test-lever round, the single run met the gate whenever the designed margin was at least about 20 pp. Sentinel attempt 7: tests margin 19.3, final margin 19.9. The 2e46 pair: run A cleared final by only 4.4.
- Rule of thumb: **push on one run only if the predicted, oracle-anchored margin is ≥ 20 pp final and ≥ 1 lever family the blind reads lose.** Otherwise expect about a 50% chance that the next run lands on the wrong side.
- Predictions to compare against: cold-chain DESIGN.md predicts all-but-one 80.0 <= 92 and judge 31-40%. schema predicts lever 16.6% of positive points. metered predicts lever 16.3% and the probe program 0/48 -> 83.7 (DESIGN.md:30). On tests alone, each is about one variance band below 100. That is enough for tests < 100 only if the agent misses the whole lever, which is what the blind reads are for (LEVER_RULES_v3.md:200, :211).
