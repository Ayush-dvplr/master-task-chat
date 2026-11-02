# DESIGN c3aca8d flood-repair-portfolio harden-a1: NO CORE

BUNDLE untouched (tree cd11476e6e14). Kill table and logs: `master_chat_work/bundles/_work/flood-repair-portfolio/h1_a1/KILL_TEST.md`, `_runs/20261031/flood-repair-portfolio/harden-20261031T1420/` (bench1-6, book7a/b, book8a/b, fuzz1). Diagnosis: `TRIP.md`.

## 1. Arithmetic
- Gate v3.7: tests < 85, rubric < 85, final < 40. Attempt 1: tests 100.0, judge 13.33, final 56.66.
- Target pred final <= 35 with judge mid 13.33 (judge unchanged): tests <= 56.67% of 108 = a1 must lose >= 47 points.
- Lever checks: hidden H1-H3 per-book checks 3 x 25 = 75 of 108 positive points (69.4%, bar >= 40%). If a1 loses all 75: tests 30.6, final 22.0.
- Verifier: timeout_sec 2700 (task.toml), 90% = 2430 s; target 900-1,200 s. A 100-round hidden book costs about 15-30 s for the verifier min-fill reference plus at most 20 s per program run; 3-4 such books fit easily.

## 2. Designs tried (generator family unchanged: bookgen.make_book, `_lattice` rounds, own seeds)
1. Shorter stated limit on current hidden books. ref busy max 0.36 s -> limit >= 1.44 s; strongest plain exact (vebest) max 0.63 s keeps every book. a1 1.60-10.40 s would lose. Fails bar (e).
2. Redesign 1, bigger hidden books: K = 30/100/105/110 large lattice rounds per book (140-150 rounds, mean 349-389 conflict edges per large round; inside contract.md:11-12 caps of 200 rounds, 160 rows, 900 records). Stated limit stays 20 s (contract.md:15). ref 1.6-5.2 s; a1 and dae9563 TIMEOUT on every book; verifier min-fill VE 10.9-30.6 s (loses 3/8 eligible books); vebest 9.8-24.6 s, loses only k100a (21.06 s, 5% over). Fails bar (e): strongest plain exact keeps >= 85% of lever points, and its single loss is inside host noise (20-25% run to run).
3. Redesign 2, documented structure mix: rows 8-20 x diagonal share 0-1.0 (contract permits any conflict shape inside the caps). Best VE / ref per 160-node round 0.6-3.4x, never > 3.5x. No mix makes the strongest plain exact solver robustly > 4x ref, which is the minimum since ref must stay <= 1/4 of the limit with both cores busy.

## 3. Why no core
The reference (solution/solve.py:183-243, BFS frontier sweep DP) and an elimination-order variable-elimination DP (min-degree or min-fill, split into independent parts) are the same width-bounded DP class. Their gap is a constant factor (per round 0.6-3.4x, per book 4.2-8.6x), smaller than or equal to the 4x headroom the 1/4-limit rule demands. A program using both cores (task.toml cpus 2) would halve its time again. So any size, density, structure mix or limit that keeps ref <= 1/4 limit lets a careful plain exact solver pass most books. The paid agent's program (elimination-order B&B + memo) is 10-75x slower than ref per round and would die on bigger books, but the lever then separates "a1's search" from "DP", not "generic search" from "elimination-order DP", as note 6 requires.

## 4. Kill table (a1 row first; best design = k100-style books at 20 s; 75 lever points)
| program | lever kept | kind | evidence |
|---|---|---|---|
| a1 (paid run) | 0/75 | TIMEOUT | TIMEOUT@60 on k100a-c, @40 on t1-t6 |
| dae9563 (blind) | 0/75 | TIMEOUT | TIMEOUT@60 on k100a-c |
| split-into-parts + verifier min-fill VE | about 47/75 | TIMEOUT | 3/8 eligible books over 20 s |
| vebest (strongest plain exact, min-degree/min-fill VE) | 50-75/75 | TIMEOUT | 1/8 books over 20 s by 5% |
| first-write, all-but-one | not run | - | stopped at NO CORE |
Every finished run EXACT; a1 also 150/150 MATCH on fuzz books (no WRONG to grade). Shipped book fast for all (a1 2.2 s).

## 5. Predicted run score (if the master accepts the near-miss anyway)
k100-style hidden H1-H3 at 20 s: a1-like program tests about 30.6, judge 13.33, final about 22. A run that writes a VE DP (as the verifier itself does) keeps 75-100% of hidden points: tests 77-100, final 45-57. Spread too wide to call; this is why the bar fails.

## 6. Judge and docs
Judge unchanged. Docs unchanged (no edit made). No bundle file changed.

## Lessons for the master
- frontier DP vs elimination-order DP is a constant factor below the 4x headroom; speed levers on lattice rounds cannot separate them | template_change: LEVER_RULES_v3.md 1C (add: check best plain DP / ref ratio > 4x before choosing a speed lever)
- a1 kept 150/150 fuzz books exact; flood has no correctness gap left to grade | no change: measured
- near-miss option (100-round hidden books) kills a1 and the blind but not a careful VE; needs an explicit waiver of bar (e) | no change: Ayush decision
