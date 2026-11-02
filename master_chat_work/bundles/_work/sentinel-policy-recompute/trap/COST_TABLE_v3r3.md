# COST_TABLE sentinel-policy-recompute (P12 v3 r3, AFTER tests, P = 33)

Measured with WORK/single_lever.py and WORK/rule_mutants.py on the oracle output, local scorer, tests channel only.

## One fact wrong (each lever alone)

| lever | one fact wrong (variant) | points lost | share of P | tests failed |
|---|---|---|---|---|
| L3 allowance across principals | no allowance (m2b) / allowance per principal (m2) | 18 | 0.545 | policy 5, curve 5, trace 5, mutation_allowance 3 |
| L2 rev 1 seconds | raw timeout (m3) / abs(v) < 100 seconds (m3b) | 10 | 0.303 | policy 5, trace 5 |
| L7 per-term rounding | rounding once over the sum (m1) | 8 | 0.242 | curve 5, mutation_risk 3 |
| L1 controls over every stored row | stored controls trusted (m13) | 5 | 0.152 | trace 5 |

## All but one right (overall)

overall = (tests + rubric) / 2 at rubric 90; G10 wants every row below 70.

| only this lever wrong | tests | overall at rubric 90 | below 70 |
|---|---|---|---|
| L3 | 45.5 | 67.7 | yes |
| L2 | 69.7 | 79.8 | no |
| L7 | 75.8 | 82.9 | no |
| L1 | 84.8 | 87.4 | no |

## G10

FAIL: L7 (0.242) and L1 (0.152) lose under 25% alone; L2, L7, L1 rows are 70 or above overall. Before (P = 31) the same gate also failed (L7 0.258, L1 0.161; L2, L7, L1 rows above 70). Report only, no levers added (prompt: out of scope).
