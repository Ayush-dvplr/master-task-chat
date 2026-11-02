# COST_TABLE - district-heat-flex-procurement (redesign r4, G10)

Measured 25 Oct 2026 with the embedded `tests/test_output.py` (positive 173, tests channel, local stub grader). Each row is the oracle with exactly the named wrong reading (OUT/proto/proto_oracle.py flags, the same readings as the verifier reference flags) run as the agent program. Rubric for "overall" taken as the measured 62.5 of the last harness run (and 90 as the rule default).

| lever | wrong reading | tests earned | tests % | points lost | share lost | overall @62.5 | overall @90 | gate >= 25% |
|---|---|---|---|---|---|---|---|---|
| M1 grants re-share (H7) | REENTRY: survivors' claims fit -> pay claims | 128 | 73.99 | 45 | 26.0% | 68.2 | 82.0 | PASS |
| M1 | DROPLEFT: survivors keep first share | 125 | 72.25 | 48 | 27.7% | 67.4 | 81.1 | PASS |
| M1 | NODROP: minimum ignored | 150 | 86.71 | 23 | 13.3% | 74.6 | 88.4 | secondary slip, not the lever reading |
| M2 allowance holder (H6) | CHAIN1: one hop of draws_from | 118 | 68.21 | 55 | 31.8% | 65.4 | 79.1 | PASS |
| M2 | CHAIN0: column ignored | 73 | 42.20 | 100 | 57.8% | 52.4 | 66.1 | (visible tests fail too) |
| M3 credited relief (H3) | RELIEF: relief ticks | 115 | 66.47 | 58 | 33.5% | 64.5 | 78.2 | PASS |
| CARRY (amplifier, counts 0) | NOCARRY | 107 | 61.85 | 66 | 38.2% | 62.2 | 75.9 | amplifier |

Two-lever rows: REENTRY+CHAIN1 98 (56.6%); REENTRY+RELIEF 110 (63.6%); CHAIN1+RELIEF 85 (49.1%); REENTRY+NOCARRY 107 (61.8%); all three 85 (49.1%).

"All but one right" (one lever misread, others right) = the single rows above: tests 66-74, overall at the measured judge 62.5 = 64.5-68.2 (< 70). At the default rubric 90 the rows sit at 78-82 (the gate tests < 140 - rubric holds only for rubric <= 66).

CL-4 one-fact-wrong honesty: each main misread costs 26-34% (inside the 25-45% band); losses fall only on the hidden `_hard` families whose owned rows the rule changes (REENTRY fails 9 tests, CHAIN1 11, RELIEF 12), never on visible tests (W5).

Saved agent programs: blind 31/173 = 0.179, harness 28/173 = 0.162.

Differential fuzz (final generator, `OUT/proto/fuzz_final.py 320 6000`): see `OUT/redesign_r4/proto/fuzz_final_6000_320.log`; REENTRY, DROPLEFT, NOCARRY, CHAIN1, RELIEF differ on 100% of the corpora where they apply (H1 + H2 for M1/M3/CARRY, H1 for M2); blind and harness programs differ on 100%.

## Wave 1 hardening (board 7d95b18, 27 Oct 2026): measured in Docker
Embedded `tests/test_output.py` (58 checks, positive 205), `grade.py` with the stub rewardkit, env image,
2 CPU, 4 GB, one program at a time (`proto/cost_in_docker.sh`, raw lines `COST_w1.txt`). Each program is
the agent program as a whole (solver variants = bundle solve.py with only the portfolio search replaced).

| program | tests earned | tests % | wide points kept (of 32) | grader s |
|---|---|---|---|---|
| oracle (bundle solve.py) | 205 | 100.0 | 32 | 78 |
| first write = all-but-one (pre-wave solve.py, plain search, every other rule right) | 173 | 84.4 | 0 (late) | 252 |
| opus probe 9 program | 173 | 84.4 | 0 (late) | 1173 |
| blind 8caff6e program | 31 | 15.1 | 0 (late) | 247 |
| greedy (cheapest per relief tick) | 66 | 32.2 | 6 (feasible only) | 20 |
| merit order (bid cost) | 66 | 32.2 | 6 (feasible only) | 19 |
| naive (all portfolios) | 173 | 84.4 | 0 (late) | 250 |
| dp (time-indexed state merge) | 173 | 84.4 | 0 (late) | 249 |
| bnb (LP-style bound, ties one by one) | 173 | 84.4 | 0 (late) | 247 |
| bnb_ord (best-first order, no merge) | 173 | 84.4 | 0 (late) | 249 |
| ref (identical offers merged, no order) | 173 | 84.4 | 0 (late) | 251 |
| ref3 (state merge plus bound) | 173 | 84.4 | 0 (late) | 248 |

The lever alone costs 32 of 205 = 15.6% (inside 10-30%); all-but-one 84.4 (<= 92). Greedy and merit also
fail old portfolio checks (wrong selections on shipped and hidden extracts). Grader time stays far under
the 2700 s verifier timeout (worst 1173 s, the probe-9 program, whose runs end at the 120 s limit).

## Gate v3.6 harden (board dcd21a3, 28 Oct 2026): measured in Docker on the final tests (66 checks, positive 237)
grade.py with the stub rewardkit on the bundle tests/test_output.py, env image, 2 CPU, 4 GB, one program per
container at a time (two containers). Raw: WORK/g36/cost/COST_A.txt, COST_B.txt, cost_<program>.txt.
Lever = 16 wide checks (64 pts, 27.0%); new part = wide_2_*, wide_3_* (32 pts).

| program | tests /237 | % | wide pts kept /64 | new wide kept /32 | loss kind | grader s | shipped inputs fast |
|---|---|---|---|---|---|---|---|
| oracle (bundle solve.py) | 237 | 100.00 | 64 | 32 | - | 45 | yes |
| a10 agent program (run a10) | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| blind ef9234c | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| blind d62d21c | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| blind 7dd7290 | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| first write = all-but-one (pre-wave solve.py, plain search, every other rule right) | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| opus probe 9 | 173 | 73.00 | 0 | 0 | TIMEOUT | 485 | yes |
| blind 8caff6e | 31 | 13.08 | 0 | 0 | TIMEOUT | 485 | yes |
| greedy (cheapest per relief tick) | 72 | 30.38 | 12 | 6 | WRONG | 26 | yes |
| merit order | 72 | 30.38 | 12 | 6 | WRONG | 25 | yes |
| naive | 173 | 73.00 | 0 | 0 | TIMEOUT | 487 | yes |
| dp (state DP) | 173 | 73.00 | 0 | 0 | TIMEOUT/CRASH | 388 | yes |
| bnb (LP-style bound) | 173 | 73.00 | 0 | 0 | TIMEOUT | 486 | yes |
| bnb_ord | 173 | 73.00 | 0 | 0 | TIMEOUT | 486 | yes |
| ref (merge only, no order) | 189 | 79.75 | 16 | 16 | TIMEOUT on wide_0/1/2; wide_3 passed inside 120 s | 490 | yes |
| ref3 (DP plus bound) | 173 | 73.00 | 0 | 0 | TIMEOUT | 486 | yes |

Bar (LEVER_RULES v3.6): first write and all-but-one 73.0 (<= 75); a10 and the three P13 blinds 73.0 each (<= 80);
every generic solver loses >= 75% of the 64 lever points (ref merge-only is the weakest at 48/64 lost, borderline
on wide_3: 120.01 s in the kill run, inside 120 s in the grader run). Single wrong readings (trap run,
WORK/p12/dout/TRAP_g36.txt): REENTRY 192, CHAIN1 182, RELIEF 179 of 237. Worst grader 490 s vs 2700 s verifier
timeout. Predicted a10-like run: tests 73.0, rubric 16.67 (judge unchanged), final 44.8.

## Gate v3.6 judge harden (board 8d509b8, 28 Oct 2026)
No test, solver or kill-test re-run (brief: tests restated from a11, 173/237 = 73.0). Judge positive 24 (R1-R4, R8-R10
w3 = 21, R5, R6, R11 w1 = 3), negative R7 -5. Predicted rubric from positives, per criterion in OUT HARDEN_REPORT:
a10 3/24 = 12.5% (was 9/24 + R7 -5), a11 3/24 = 12.5% (was 15/24); upper 6/24 = 25%. Predicted final mid
(73.0 + 12.5)/2 = 42.75, worst (73.0 + 25.0)/2 = 49.0. Probe band 21/24 = 87.5% of positive, predicted mid 12.5%.

## P12 fix ql1 (session 8556721, 29 Oct 2026)
Tests positive stays 237. a12 and a11 agent programs re-graded with the P12 tests: 173/237 = 73.0 each (only the 16
wide_* checks fail, by timeout). Judge positive 27 (R3 split into R3 + R12, w3 each); a11 judged acts R5, R6, R11
give 3/27 = 11.1%. Predicted a12-like final mid (73.0 + 11.1)/2 = 42.05.
