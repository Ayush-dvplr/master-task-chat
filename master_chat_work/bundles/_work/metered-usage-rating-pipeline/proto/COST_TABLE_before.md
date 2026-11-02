# COST_TABLE (G10 + CL-4) for metered-usage-rating-pipeline, harden round 2

Measured 25 Oct 2026 01:07 IST by `WORK/cost_table.py` on the round-2 bundle: each wrong reading is
patched into a copy of `solution/solve.py`, the copy is delivered as `/app/out/transform.py` in a
scratch app root, its shipped outputs are written, and every registered check of the real
`tests/test_output.py` (hidden seed 58213) is run. Positive test points 247. Raw numbers:
`WORK/cost_table.json`. Overall below = 0.5 x tests + 0.5 x judge, judge taken at the probe-2
measured 70.59.

| lever | wrong reading injected (habit) | alone: points lost | alone: tests failed | this lever right, the other two wrong: tests / overall | one fact wrong: points lost | G10 |
|---|---|---|---|---|---|---|
| LV-MU-6 (A) | second credit pass re-enters the at-or-below branch: when the held lines' summed charge is at or below the pool each held line gets its own charge (H7) | 65 / 247 = 26.3% | 13 | 46.2 / 58.4 | 25 = 10.1% (5 tests): one held line given its own charge | PASS alone; one fact under 25% |
| LV-MU-5 (B) | billing group = the parent named on the row (one level), not the top of the parent chain (H6) | 133 / 247 = 53.8% | 27 | 61.5 / 66.1 | 133 = 53.8% (27 tests): one depth-2 account grouped under its direct parent | PASS |
| LV-MU-7 (C) | second true-up pass re-computes the shortfall from the held lines (minimum - held charge) instead of sharing every cent of the shortfall (H7) | 65 / 247 = 26.3% | 13 | 46.2 / 58.4 | 30 = 12.1% (6 tests): one held line given its re-computed share | PASS alone; one fact under 25% |

All three wrong: 133 / 247 = 53.8% lost (B's cascade covers every hard document A and C touch).
A and C wrong, B right: 95 / 247 = 38.5% lost (tests 61.5).

A and C use the same habit (H7 re-entry). A fresh agent that gets one right will likely get both
right, so the realistic outcomes are: all right 100; B wrong only 46.2; A and C wrong only 61.5;
all wrong 46.2.

Graded noise (r1 levers kept as rules with planted cases, not counted as levers):

| rule | wrong reading | alone: points lost | tests failed |
|---|---|---|---|
| LV-MU-1 north `units` a JSON integer | quoted digit strings accepted | 209 / 247 = 84.6% | 51 |
| LV-MU-3 committed account by accounts.csv plan | plan in force at the line | 118 / 247 = 47.8% | 24 |

## One fact wrong

- LV-MU-6 and LV-MU-7 one fact wrong cost 10.1% and 12.1%, under 25%. One wrong credit or true-up
  changes its own line, its region document, one segment, product_summary and summary; nothing else
  reads it (no coupling back into other lines), so the honest count stays small. The instruction keeps
  "Each output document is judged whole and exactly against the contract" (CL-4 exemption);
  reported, not tuned.
- LV-MU-5 one fact wrong costs the same as alone (53.8%): one account rated in the wrong group moves
  tier counters of every later line of both groups, which moves charges, the region credit base
  (COUPLING) and so every credit and true-up of the region, and the tier-scale mutation run.

## Coupling

The coupling quantity is the region credit base (rating_contract.md glossary lines 30-31). It feeds
both the credit share (Credit, lines 162-177) and the shortfall (True-up, lines 179-189), so one
charge slip reaches every credit and true-up of its region. No check carries a weight above 5.
