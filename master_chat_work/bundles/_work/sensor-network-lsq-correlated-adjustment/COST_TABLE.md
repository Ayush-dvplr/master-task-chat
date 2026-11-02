# COST_TABLE (G10), redesign r2 4d6dfe8

Each row is `solution/solve.py` with exactly the named wrong readings patched in (`OUT/proto/variants.py`, raw `OUT/proto/variants.json`), scored with the real tests (P = 86). Overall = (tests + rubric) / 2 at rubric 90 (not measured) and at the predicted rubric when the matching R9-R11 recompute is skipped (judge 21/24 = 87.5) or all three are skipped (15/24 = 62.5).

| row | wrong reading | tests | tests lost | overall @90 | overall @62.5 | gate (>= 25% lost alone; overall < 70) |
|---|---|---|---|---|---|---|
| oracle | none | 86/86 = 100.0 | 0 | 95.0 | n/a | n/a |
| A alone (H7) | second pass re-enters the fits branch | 63/86 = 73.3 | 23 (26.7%) | 81.6 | 67.9 | 25% PASS; < 70 only with skipped recomputes |
| B alone (H6) | centring one level deep | 63/86 = 73.3 | 23 (26.7%) | 81.6 | 67.9 | 25% PASS; same |
| C alone (H3) | district from line region | 63/86 = 73.3 | 23 (26.7%) | 81.6 | 67.9 | 25% PASS; same |
| A+B, A+C, B+C | two of the above | 40/86 = 46.5 | 46 | 68.3 | 54.5 | < 70 PASS |
| A+B+C | all three | 17/86 = 19.8 | 69 | 54.9 | 41.1 | < 70 PASS |
| a2 agent program | predates all three rules | 8/86 = 9.3 | 78 | n/a | n/a | reflex gate <= 0.20 PASS |

One-fact-wrong (CL-4): each lever alone costs one hidden extract's six whole-document families (18) plus its own `_hard` test (5) = 23 of 86 = 26.7%, inside the 25-45% band. The visible shipped test of each family passes under its wrong reading (W5: shipped data separates no reading).

"All but one right" at rubric 90 is 81.6, above 70: the gate holds only when the run also skips the matching recompute (R9, R10 or R11) and another conduct criterion, which is the measured Opus habit (a2 judge 12/15). Recorded, not hidden.
