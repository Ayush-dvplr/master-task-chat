# KILL_TEST c3aca8d harden-a1 (Docker, --memory 4g --cpus 2; logs _runs/20261031/flood-repair-portfolio/harden-20261031T1420/)

Programs (all in WORK/h1_a1): a1 = a1_program/derive_report.py (split + B&B + memo, min-degree order); dae = dae9563_program.py (plain memo branch-and-reduce); elim = elim_program.py (a1 I/O + verifier min-fill VE `_portfolio`, split into parts); vebest = vebest_program.py (split into parts, min-degree order, min-fill if cheaper, VE over independent subsets; strongest plain exact); ref = solution/solve.py. Every finished run EXACT; no WRONG, no CRASH anywhere. Prototype worlds from bookgen.make_book via proto_gen.py (own seeds 901-926), K = large lattice rounds per book.

## Redesign 0: current hidden books (20 s), book7a/b
| book | ref busy | a1 | dae | elim | vebest |
|---|---|---|---|---|---|
| H1 | 0.36 | 10.40 EXACT | 54.30 TIMEOUT@20 | 0.67 | 0.63 |
| H2 | 0.25 | 6.14 | 43.66 TIMEOUT@20 | 0.60 | 0.38 |
| H3 | 0.15 | 1.60 | 24.40 TIMEOUT@20 | 0.31 | 0.32 |
| M | 0.13 | 2.62 | 5.10 | 0.21 | 0.21 |
Shorter limit L (ref busy <= L/4 -> L >= 1.44 s): vebest max 0.63 s keeps every book at any allowed L. Fails bar.

## Redesign 1: many large rounds per hidden book, 20 s (bench3, book7, book8)
| book (seed,K,n,rows) | ref busy | ref | a1 | dae | elim | vebest |
|---|---|---|---|---|---|---|
| b13a 901,30,160,13 | - | 1.14 | TIMEOUT@90 | TIMEOUT@90 | 7.13 | - |
| b12a 902,30,160,12 | - | 1.54 | 57.18 | TIMEOUT@90 | 11.07 | - |
| b14a 903,30,156,14 | - | 1.32 | 74.49 | - | 7.98 | - |
| k100a 911,100,160,13 | 4.19 | 4.67 | TIMEOUT@60 | TIMEOUT@60 | 26.43 | 21.06 |
| k100b 912,100,156,14 | 4.15 | 2.48 | TIMEOUT | TIMEOUT | 13.98 | 19.15 |
| k100c 913,100,160,11 | 4.46 | 3.68 | TIMEOUT | TIMEOUT | 18.81 | 19.46 |
| t1 921,105,160,13 | 4.19 | 5.23 | TIMEOUT@40 | - | 30.60 | 24.63 |
| t2 922,105,156,14 | 3.28 | 2.80 | TIMEOUT | - | 19.26 | 18.39 |
| t3 923,105,148,12 | 2.73 | 1.62 | TIMEOUT | - | 10.89 | 9.81 |
| t4 924,110,160,14 | 3.14 | 1.72 | TIMEOUT | - | 12.52 | 11.39 |
| t5 925,110,152,14 | 3.29 | 1.69 | TIMEOUT | - | 21.59 | 14.46 |
| t6 926,110,144,12 | 4.65 | 4.44 | TIMEOUT | - | 22.42 | 18.49 |
At 20 s with ref <= 5 s in every measurement: a1 and dae lose every book; elim loses 3/8 (k100a, t5, t6; k100c 18.81 and t2 19.26 kept narrowly; t1 excluded since ref 5.23 > 5); vebest loses 1/8 (k100a, by 1.06 s = 5%). vebest/ref per book 4.2-8.6x; host noise (foreign containers) moves single runs by 20-25%.

## Redesign 2: documented structure mix (rows 8-20, diagonal share 0-1.0), per 160-node round (bench1, bench5, bench6)
Best VE (min of min-degree, min-fill) / ref per round: 0.6-3.4x, never above 3.5x; plain linear sweep over an elimination order TIMEOUT@60 (bench4). No mix found where the strongest plain exact solver is robustly > 4x ref.

## Lever points kept (3 hidden books x 25 = 75 lever points), best case design k100-style books at 20 s
| program | lever points kept | loss kind |
|---|---|---|
| a1 | 0/75 (predicted) | TIMEOUT |
| dae9563 | 0/75 (predicted) | TIMEOUT |
| elim (verifier min-fill VE) | about 47/75 (3/8 books lost) | TIMEOUT |
| vebest (strongest plain exact) | 50-75/75 (0-1 books lost, 5% margin) | TIMEOUT |
Not run: first-write and all-but-one programs on prototype worlds (stopped at NO CORE before Phase 3).
Verdict: strongest plain exact solver does not robustly lose >= 15% of lever points (bar note 6 / LEVER_RULES v3.7 (e)). NO CORE.
