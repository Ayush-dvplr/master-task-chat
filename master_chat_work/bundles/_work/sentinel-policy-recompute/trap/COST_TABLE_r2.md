# COST_TABLE sentinel-policy-recompute (Harden round 2, P = 44)

Measured with WORK/single_lever.py on the oracle output (one exact edit to the repaired cli.py per row), local scorer, tests channel only. Previous table (P12 v3 r3, P = 33): WORK/trap/COST_TABLE_v3r3.md.

## Each lever alone and one fact wrong

| lever | reading | earned / 44 | points lost | share of P | tests failed |
|---|---|---|---|---|---|
| N1 region override allowance | lever off (no allowance) | 21 | 23 | 0.523 | region_hard 5, policy 5, curve 5, trace 5, mutation_allowance 3 |
| N1 | one fact wrong: counter per tenant (region value) | 21 | 23 | 0.523 | same |
| N1 | one fact wrong: one counter for every row | 24 | 20 | 0.455 | region_hard 5, policy 5, curve 5, trace 5 |
| N2 timeout unit by version cutover | lever off (raw value) | 29 | 15 | 0.341 | cutover_hard 5, policy 5, trace 5 |
| N2 | one fact wrong: unit taken from rev | 29 | 15 | 0.341 | same |
| N3 window admit count | lever off (no admits) | 21 | 23 | 0.523 | admit_hard 5, policy 5, curve 5, trace 5, mutation_risk 3 |
| N3 | one fact wrong: admits drawn by the resolved tenant only | 21 | 23 | 0.523 | same |
| COUPLING draw_order | region refusal still draws an admit | 29 | 15 | 0.341 | policy 5, curve 5, trace 5 |
| COUPLING draw_order | window refusal still draws a region unit | 29 | 15 | 0.341 | policy 5, curve 5, trace 5 |
| L7 per-term rounding (noise) | rounding once over the sum | 36 | 8 | 0.182 | curve 5, mutation_risk 3 |
| L1 controls over every stored row (amplifier) | stored controls trusted | 39 | 5 | 0.114 | trace 5 |
| carried: row version gate | row version ignored | 29 | 15 | 0.341 | policy, curve, trace |
| carried: half-open window | inclusive end | 29 | 15 | 0.341 | policy, curve, trace |
| carried: every passing row applies | first passing row only | 16 | 28 | 0.636 | cutover_hard, admit_hard, policy, curve, trace, mutation_risk |
| probe-1 reading (own tenant rows, region value, no admits) | combined | 13 | 31 | 0.705 | region_hard, admit_hard, policy, curve, trace, mutation_risk, mutation_allowance |

## All but one right (overall)

overall = (tests + judge) / 2. Measured judge = 19/37 = 51.35 (probe 1 16/37 plus 3 for the R11 rewrite). Rubric 90 shown as information.

| only this lever wrong | tests | overall at measured judge 51.35 | below 70 | overall at rubric 90 |
|---|---|---|---|---|
| N1 (per tenant) | 47.7 | 49.5 | yes | 68.9 |
| N1 (one counter) | 54.5 | 53.0 | yes | 72.3 |
| N2 | 65.9 | 58.6 | yes | 78.0 |
| N3 | 47.7 | 49.5 | yes | 68.9 |
| draw_order (either direction) | 65.9 | 58.6 | yes | 78.0 |

## G10

PASS at the measured judge: N1, N2 and N3 each lose at least 25% of P alone and with one fact wrong (N1 45.5-52.3%, N2 34.1%, N3 52.3%); every all-but-one row is under 70 at judge 51.35. At rubric 90 only the N1 per-tenant and N3 rows are under 70 (information, as on match-replay). L7 and L1 stay as graded noise and amplifier, not as counted levers.

## Reflex gate (probe-1 agent program, OUT/agent_program, adapted only for the region-key lookup)

| mode | score |
|---|---|
| delivered out/ with adapted cli.py in tool.zip | 0.1591 (7/44) |
| agent build.py rerun with adapted cli.py | 0.1818 (8/44) |
| unadapted original | 0.1364 (6/44) |

All <= 0.20: PASS. It earns cli_init_and_set 3, validate 3, rerun 1 (+ shipped 1 in build mode) and fails all six hidden w5 tests and both mutation tests.
