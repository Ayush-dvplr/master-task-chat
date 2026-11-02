# DESIGN flood-repair-portfolio harden r3 (c510591): NO CORE

Bundle untouched: tree sha 931f8f817d76 before and after this round. Docs changed: no.

## Why no core
Route 1 needs a held-out hidden book that fires a documented branch the paid attempt-3 program
mishandles (route1 notes R4, L2). The search found none (TRIP.md fuzz table):
- 1,500 generator books (300 seeds in each of five profiles covering every generator branch:
  random mix, all 19 fault kinds, twin and path ties, large lattice rounds, shipped declared order):
  1,500 MATCH, 0 DIFF.
- 47 targeted documented cases the generator never plants, on 3 base books each (141 runs):
  126 MATCH, 15 identical MISSING_FILE failures, 0 DIFF; 115 of the runs change the reference
  output, so the cases do fire.
- Full code read of the a3 program against solution/solve.py: every check order, rejection code,
  tie rule and document shape of contract.md:19-78 matches; the solver is exact on every path.
  Remaining differences sit only on behaviours no shipped document states (duplicate register
  keys first-wins vs last-wins, whitespace-only lines, short rows, BOM, `:` INI delimiter); planting
  any of them would grade an unstated convention (COMMON_RULES_v5, LEVER_RULES 0b, section 8).

## Arithmetic (why the judge and the time sentence cannot carry the gate alone)
| program | tests now | tests after any route-1 change without a WRONG check | judge mid floor | final floor |
|---|---|---|---|---|
| a3 | 108/108 = 100.00 | 100.00 (EXACT on H1-H3 at 5.2-8.3 s, limit 20 s) | 0 | (100 + 0) / 2 = 50.00 > 40 |
| a1 | 30/108 = 27.78 | 27.78 (TIMEOUT on H1-H3) | not regraded this round | 13.89 at judge 0; under 40 for any judge mid below 52.22 |

Even a judge rebuild that scores the a3 trajectory 0 leaves a3 at tests 100 > 85 and final 50 > 40.
The timeout lever cannot be widened: master note 1 forbids lowering the 20 s limit or growing the
books further (reference 1.2-2.1 s busy against a3 5.2-8.3 s, under the 4x gap), and a3 is already
inside the limit with more than 2x headroom. Lever share (new WRONG + timeout) for a3 = 0 of 108.

## Measured table (reused, a3_score/A3_SCORE.md; no new timing run needed for NO CORE)
| program | H1 s | H2 s | H3 s | result | lever points kept of 78 |
|---|---|---|---|---|---|
| reference (busy) | 1.78 | 1.93 | 2.11 | EXACT | n/a |
| a3 (busy) | 6.96-7.58 | 7.29-7.58 | 5.21-5.29 | EXACT x3 | 78 |
| a1 (harden r2 kill2) | T@60 | T@60 | T@60 | TIMEOUT x3 | 0 |

## Not done (stopped at NO CORE as the prompt orders)
Judge rebuild, time-budget sentence, hidden-book prototypes and the kill table on new checks were
not built: without a WRONG check none of them can bring a3 under the gate. Suggested sentence held
for a later route (option 2 of A3_SCORE): "Leave enough of that time to finish and write your final reply."

NO CORE: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/harden_r3/DESIGN.md
