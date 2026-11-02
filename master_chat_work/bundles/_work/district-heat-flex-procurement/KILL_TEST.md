# Wave 1 (7d95b18) kill test, P-3 wide event-regions

Docker, env image `district-heat-flex-procurement__eh2yzcy__env-main`, `--cpus 2 --memory 4g`,
two programs at a time, `timeout 120` per whole program run on one extract (the stated limit).
Points = the 16 points the lever carries per corpus: feasible 3, selection 5, tie_decisions 5, intervals 3
(`proto/score.py` against the ref2 output). LATE = killed at 120 s, keeps 0.

Generator: `proto/gen.py` (composed offer family of the hidden generator; every event-region 20-26 sites,
1-2 offers per site plus an identical copy of one of them 95% of the time, targets 60-110% of the
largest reachable relief, relief ceilings 150-190% of it, 25% flat events, no allowance limits).
`proto/guard.py` re-draws an event-region (own sub-seed) while its reference node count exceeds 150,000.

Solvers (`proto/solvers.py`, plugged into solution/solve.py by `proto/run_prog.py`):
- greedy: cheapest bid per relief tick first, keep when the key improves.
- merit: merit-order stacking by bid cost while shortfall or deficit drops.
- naive: itertools.product over every site lane.
- dp: exact table over (relief vector, recovery vector, segment relief) states, ties counted by merge.
- bnb: branch-and-bound with optimistic shortfall and floor bound (LP-style relaxation of relief), ties visited one by one (Opus probe-9 shape).
- bnb_ord: bnb plus best-first ordering (largest relief lane and offer first, none last).
- ref: bnb plus identical offers at one site merged (count multiplied), no ordering.
- ref3: layered table over states merged plus the bnb bound as a cut (DP plus bound).
- solve: the shipped solution/solve.py (plain DFS); opus: probe-9 program; blind: 8caff6e program.
- ref2: reference (identical offers merged, best-first ordering, bound).

## e6 (6 events, 24 ERs, no guard)
| solver | e6_31 s | pts | e6_33 s | pts |
|---|---|---|---|---|
| ref2 | 2.77 | 16 | 1.58 | 16 |
| greedy | 0.39 | 3 | 0.39 | 3 |
| merit | 0.41 | 3 | 0.39 | 3 |
| naive, dp, bnb, blind, solve, opus, bnb_ord | LATE | 0 | LATE | 0 |
| ref | 77.19 | 16 | 69.37 | 16 |
| ref3 | 118.65 | 16 | LATE | 0 |
Verdict: too small (ref and ref3 exact inside the limit). Moved to more events.

## e10 (10 events, 40 ERs, no guard)
| solver | e10_41 s | pts | e10_42 s | pts |
|---|---|---|---|---|
| ref2 | 7.6 / 8.73 | 16 | 10.39 / 9.93 | 16 |
| greedy | 0.69 | 3 | 0.58 | 3 |
| merit | 0.69 | 3 | 0.55 | 3 |
| naive, dp, bnb, blind, solve, opus, bnb_ord, ref3 | LATE | 0 | LATE | 0 |
| ref | 86.11 | 16 | LATE | 0 |
Verdict: ref still exact on one corpus. Moved to 20 events with the node guard (heavy tail of single ERs
up to 845k nodes removed by re-draw).

## g20 (20 events, 80 ERs, guard 150k nodes per ER)
Raw lines: `proto/dout/KILL20.txt` (ALL_DONE, run 13:50-14:10 IST, container dh_w1_kill20).
| solver | g20_61 s | exact | pts | g20_62 s | exact | pts |
|---|---|---|---|---|---|---|
| ref2 (reference) | 9.92 / 12.2 | yes | 16 | 9.49 / 10.06 | yes | 16 |
| greedy | 0.91 | no | 3 | 1.46 | no | 3 |
| merit | 0.88 | no | 3 | 1.41 | no | 3 |
| naive | LATE 120 | no | 0 | LATE 120 | no | 0 |
| dp | LATE 120 | no | 0 | LATE 120 | no | 0 |
| bnb (LP-style bound, Opus shape) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| blind 8caff6e | LATE 120 | no | 0 | LATE 120 | no | 0 |
| solve (shipped solve.py) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| opus probe 9 | LATE 120 | no | 0 | LATE 120 | no | 0 |
| bnb_ord | LATE 120 | no | 0 | LATE 120 | no | 0 |
| ref (merge only) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| ref3 (DP plus bound) | LATE 120 | no | 0 | LATE 120 | no | 0 |
Verdict: every generic solver loses >= 81% of the 16 points per corpus (13/16 greedy, merit; 16/16 the rest).
Reference max 12.2 s = 10% of the 120 s limit (<= 1/4). Regime chosen.

## Final wide corpora (as shipped in tests: wide_0 seed 75775, wide_1 seed 84071; 20 events, 80 ERs each)
Raw lines: `proto/dout/KILLF.txt` (ALL_DONE, run 15:17-15:36 IST, container dh_w1_killF, env image, 2 CPU, 4 GB,
two solvers at a time, `timeout 120`). Points = the four wide checks of that corpus (3+5+5+3 = 16).
| solver | wide_0 s | exact | pts | wide_1 s | exact | pts |
|---|---|---|---|---|---|---|
| ref2 (proto reference) | 7.77 | yes | 16 | 9.51 | yes | 16 |
| solve (new bundle solve.py) | 7.67 | yes | 16 | 11.08 | yes | 16 |
| old (pre-wave solve.py, plain search) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| greedy (cheapest per relief tick) | 0.54 | no | 3 | 1.03 | no | 3 |
| merit (bid cost order) | 0.50 | no | 3 | 1.02 | no | 3 |
| naive (all portfolios) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| dp (time-indexed state DP) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| bnb (LP-style bound, Opus shape) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| blind 8caff6e | LATE 120 | no | 0 | LATE 120 | no | 0 |
| opus probe 9 | LATE 120 | no | 0 | LATE 120 | no | 0 |
| bnb_ord (best-first order, no merge) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| ref (merge only, no order) | LATE 120 | no | 0 | LATE 120 | no | 0 |
| ref3 (DP plus bound) | LATE 120 | no | 0 | LATE 120 | no | 0 |
Verdict: every generic solver loses 13/16 (81%) or 16/16 of the lever points on both corpora.
Bundle oracle max 11.08 s = 9.2% of the 120 s limit (<= 1/4).


## gate36 dcd21a3 (28 Oct 2026): new corpora wide_2 (seed 7120) and wide_3 (seed 24943)
Docker `p12env-dhfp`, `--memory 4g --cpus 2`, two programs at a time, `timeout 120` per whole program run
(the stated limit). Generator: WORK/proto/g36/tsrc_g36.py (= test_output.src.py with 4 WIDE_SEEDS and the two
new WIDE_BUMPS entries from WORK/proto/g36_guard.py, budget 150k nodes). Points = feasible 3 (with the TS-25
non-empty rule, proto/g36/score36.py), selection 5, tie_decisions 5, intervals 3. Raw: proto/g36/dout/KILL36.txt
(ALL_DONE, run 04:31-05:12 IST, container g36kill-dhfp). Script proto/g36/kill_g36.sh.

| solver | shipped s | wide2 s | wide2 kind | pts /16 | wide3 s | wide3 kind | pts /16 | lever pts kept /32 (new) | lost % | shipped inputs fast |
|---|---|---|---|---|---|---|---|---|---|---|
| ref2 (proto reference) | - | 5.72 | EXACT | 16 | 6.37 | EXACT | 16 | 32 | 0% | yes |
| solve (bundle solve.py, reference) | 1.40 | 5.49 | EXACT | 16 | 6.41 | EXACT | 16 | 32 | 0% | yes |
| a10 agent program (2c033e37) | 1.18 | 120.00 | TIMEOUT | 0 | 120.00 | TIMEOUT | 0 | 0 | 100% | yes |
| blind ef9234c (1f999dbb) | 1.25 | 120.01 | TIMEOUT | 0 | 120.00 | TIMEOUT | 0 | 0 | 100% | yes |
| blind d62d21c (9fc0f640) | 1.38 | 120.01 | TIMEOUT | 0 | 120.00 | TIMEOUT | 0 | 0 | 100% | yes |
| blind 7dd7290 (94d070f1) | 1.12 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| blind 8caff6e | 1.35 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| opus probe 9 | 1.14 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| old (pre-wave solve.py, plain search = first write) | 1.32 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| greedy (cheapest per relief tick) | 1.21 | 0.34 | WRONG | 3 | 0.37 | WRONG | 3 | 6 | 81% | yes |
| merit order (bid cost) | 1.21 | 0.35 | WRONG | 3 | 0.39 | WRONG | 3 | 6 | 81% | yes |
| naive (all portfolios) | 2.36 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| dp (time-indexed state DP) | 1.38 | 120.33 | TIMEOUT | 0 | 81.25 | CRASH (rc 137, 4 GB) | 0 | 0 | 100% | yes |
| bnb (LP-style bound, Opus shape) | 1.47 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| bnb_ord (best-first order, no merge) | 1.37 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| ref (merge only, no order) | 1.50 | 120.01 | TIMEOUT | 0 | 120.01 | TIMEOUT | 0 | 0 | 100% | yes |
| ref3 (DP plus bound) | 1.48 | 120.01 | TIMEOUT | 0 | 120.10 | TIMEOUT | 0 | 0 | 100% | yes |

Verdict: every generic solver, the a10 agent program and all four blind programs lose >= 81% of the 32 new lever
points (13/16 greedy and merit by WRONG output; the rest TIMEOUT, dp CRASH by memory on wide3). Shipped inputs
run in 1.1-2.4 s for every program. Reference solve.py max 6.41 s = 5.3% of 120 s (<= 1/4).
