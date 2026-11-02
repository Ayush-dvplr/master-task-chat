# UNIQUENESS sentinel-policy-recompute (test-hardening t2, U lever)

Every candidate divisor 6..14 (reconciliation_rules.conf:3) checked against every standing curve report (convergence_spec.txt:7), each recomputed for its role with the corpus's own draw (tests/test_output.py `evaluate` witness_amount). Columns: curve reports / resets; standing reports (seq, role, converged); divisors fitting all standing reports; divisors fitting every curve report, resets ignored (D1 misread); divisors fitting the first standing report alone (decoy); verdict. Script: $T/t2/uniq.py (output copied here).

| corpus | curves / resets | standing | fit (standing) | fit (all curves) | fit (first only) | verdict |
|---|---|---|---|---|---|---|
| shipped | 0 / 0 | none | - | - | - | iteration_divisor 10 |
| utie-a | 2 / 0 | (11 auditor 35), (20 guardian 65) | 13, 14 | 13, 14 | 13, 14 | unresolved (null) |
| utie-b | 2 / 0 | (11 auditor 35), (20 guardian 65) | 13, 14 | 13, 14 | 13, 14 | unresolved (null) |
| udecoy-a | 3 / 0 | (17 guardian 65), (23 operator_legacy 83), (29 auditor 38) | 14 | 14 | 13, 14 | 14 |
| udecoy-b | 3 / 0 | (11 auditor 35), (14 operator_legacy 82), (23 guardian 65) | 14 | 14 | 13, 14 | 14 |
| d1-a | 5 / 2 | (23 auditor 37), (26 operator_legacy 90), (29 guardian 71) | 10 | none | 10, 11 | 10 |
| d1-b | 5 / 2 | (26 guardian 70), (29 auditor 39), (32 operator_legacy 89) | 10 | none | 10 | 10 |
| d2-a, d2-b | 0 / 0 | none | - | - | - | 10 |
| combo2-a | 5 / 2 | (101 auditor 38), (107 guardian 67), (119 operator_legacy 87) | 12 | none | 11, 12 | 12 |
| combo2-b | 4 / 2 | (65 guardian 65), (107 guardian 65) | 13, 14 | 14 | 13, 14 | unresolved (null) |

utie-a and utie-b are different ledgers (witness amounts 42/76 vs 41/77) whose reported values coincide after floor rounding. No-fit case: never generated (generator rejects; IN-16 settled by the stated verdict anyway). Combo2 condition 2 (master go): in combo2 at least 2 of the Q2-Q5 wrong readings move the fitted divisor (accepted() check); Q1 changes only timeout, never a risk term, so it cannot move the fit.
