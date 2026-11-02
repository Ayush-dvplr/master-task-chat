# COST_TABLE: flood-repair-portfolio

Every row is a real wrong program (WORK/mutants/<name>.py, built from solution/solve.py) run through every check of tests/test_output.py by WORK/run_tests.py. Tests positive total 108. Overall = 0.5 x tests share + 0.5 x judge share, judge share assumed 0.90. Fault-check rule mutants (WORK/rule_mut/) are listed in RULE_COVERAGE.md.

## Each lever wrong alone

| lever | wrong program | tests kept | tests lost | checks failed | overall |
|---|---|---|---|---|---|
| LV-FP-1 | greedy_benefit (greedy by benefit) | 28/108 | 74% | 22 | 0.580 |
| LV-FP-1 | greedy_ratio (greedy by benefit per conflict) | 28/108 | 74% | 22 | 0.580 |
| LV-FP-1 | greedy_swaps (greedy + 1-swap and 2-swap search) | 25/108 | 77% | 23 | 0.566 |
| LV-FP-1 | timed_bnb (colour-bound branch and bound, incumbent at 8 s per piece) | 25/108 | 77% | 23 | 0.566 |
| LV-FP-1 | timed_ils (iterated local search, best at 8 s per piece) | 25/108 | 77% | 23 | 0.566 |
| LV-FP-1 | no_tiebreak (exact, first maximiser found) | 28/108 | 74% | 22 | 0.580 |
| LV-FP-1 | tiebreak_largest (exact, largest id list wins ties) | 28/108 | 74% | 22 | 0.580 |
| LV-FP-2 | no_crew (crew conflicts dropped) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-2 | shared_crews_too (shared crews also conflict) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-2 | no_permit (permit conflicts dropped) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-2 | withdrawn_counts (withdrawn permit rows count) | 3/108 | 97% | 31 | 0.464 |
| LV-FP-2 | no_exclusion (exclusions dropped) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-2 | site_names_ignored (site-named exclusions ignored) | 3/108 | 97% | 31 | 0.464 |
| LV-FP-2 | exclusion_one_order (exclusion read in one order only) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-3 | no_override (risk_override ignored) | 10/108 | 91% | 28 | 0.496 |
| LV-FP-3 | no_premium (site premium skipped) | 7/108 | 94% | 29 | 0.482 |
| LV-FP-3 | uplift_flat (uplift added once, not per household) | 13/108 | 88% | 27 | 0.510 |
| LV-FP-3 | no_uplift (risk uplift skipped) | 13/108 | 88% | 27 | 0.510 |
| LV-FP-4 | fixed_file_order (faults scanned in default file order) | 105/108 | 3% | 1 | 0.936 |
| LV-FP-4 | invalid_before_duplicate (INVALID_INPUT checked before DUPLICATE_PROPOSAL) | 99/108 | 8% | 3 | 0.908 |
| LV-FP-4 | first_occurrence_duplicate (duplicate reported at first occurrence) | 96/108 | 11% | 4 | 0.894 |
| LV-FP-4 | row_within_round (row numbered within round) | 93/108 | 14% | 5 | 0.881 |
| LV-FP-4 | value_before_files (NONPOSITIVE_BENEFIT before file faults) | 93/108 | 14% | 5 | 0.881 |

Gate: each core lever alone loses at least 25% of tests: met (LV-FP-1 smallest loss 74%, LV-FP-2 94%, LV-FP-3 88%).
Gate: all but one lever right, overall below 0.70: met for LV-FP-1 (worst 0.580), LV-FP-2 (0.482), LV-FP-3 (0.510).
LV-FP-4 is the secondary stated-rule lever (planned share 12/108 = 11%, within the 25% cap); its pure order mutants lose 3 to 15 points (overall 0.88 to 0.94). By design it cannot reach the 25% bar; its fault-check mutants (unknown_site_unchecked, segment_invalid_unchecked and others) lose 41 to 105 because a missed fault plans a round that should be rejected.
No negative check fired on any mutant.

## All but this lever right (worst wrong program per lever, judge 0.90)

| lever wrong | worst program | predicted overall |
|---|---|---|
| LV-FP-1 | greedy_benefit | 0.580 |
| LV-FP-2 | no_crew | 0.482 |
| LV-FP-3 | uplift_flat | 0.510 |
| LV-FP-4 | fixed_file_order | 0.936 |

## Baselines on every hidden large round (master point 4)

Docker image python:3.12-slim + scipy, --cpus=2, exact solvers capped at 20 s per round, ILS 10 s (WORK/baselines.py, logs/base_loss.log). Cell = benefit lost against the optimum (0 = exact); TO = cap reached, value is the incumbent's loss; TO* = no incumbent.

| book | round | n | optimum | greedy_w | greedy_ratio | local_swap | ils 10 s | lp_round | lp_round_ls | bnb_colour | memo+reduce+split | reduce_bnb |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | R27904 | 160 | 64060 | 8271 | 6988 | 3021 | 44 | 1038 | 961 | 5958 TO | TO* | TO* |
| H1 | R66927 | 156 | 65262 | 13166 | 8640 | 6590 | 1072 | 2440 | 1281 | 7690 TO | TO* | TO* |
| H2 | R51408 | 160 | 70398 | 9995 | 7291 | 4034 | 2876 | 3121 | 223 | 4669 TO | TO* | TO* |
| H2 | R95003 | 148 | 54752 | 10158 | 5789 | 4252 | 1449 | 2230 | 924 | 4683 TO | TO* | TO* |
| H3 | R13512 | 152 | 58904 | 11518 | 6977 | 4239 | 808 | 3330 | 712 | 5892 TO | TO* | TO* |
| H3 | R60496 | 144 | 64393 | 14160 | 8539 | 4797 | 2921 | 0 | 0 | 6659 TO | TO* | TO* |
| M | R70125 | 150 | 56172 | 9889 | 7304 | 4717 | 1591 | 2258 | 1742 | 2959 TO | TO* | TO* |

Every hidden book has at least one large round where lp_round_ls and the 10 s ILS are not exact (H1 both, H2 both, H3 R13512), so every baseline loses the book's optimal, summary, policy_audit, regions and segments checks (25 of 25 optimality-dependent points per book). Seeds h1_1 (lp_round_ls exact on both large rounds) and the non-unique candidates h1_2, h3_3, h3_4 were rejected.

## Runtime in Docker (master point 2)

Pinned python:3.12-slim, solution/solve.py run with python3 -I -S three times per book (tmp/time_ref.py, logs/time_ref_cpus1.log, logs/time_ref_cpus2.log).

| book | --cpus=1 | --cpus=2 (harness) |
|---|---|---|
| SHIPPED (192 rounds, 2 large) | 0.16 to 0.49 s | 0.16 to 0.25 s |
| H1 | 0.08 s | 0.08 to 0.12 s |
| H2 | 0.09 to 0.12 s | 0.09 to 0.10 s |
| H3 | 0.08 to 0.10 s | 0.08 to 0.09 s |
| M | 0.05 to 0.06 s | 0.05 to 0.07 s |

Stated limit 20 s per book (contract.md line 15, test BOOK_SECONDS). Reference worst 0.49 s = 1/40 of the limit (gate <= 1/4 met; limit >= 3x oracle met). The generic exact solvers are single threaded, so the core count does not change them: colour bound branch and bound, memo + reductions + component split and reduce_bnb all hit the 20 s cap on every hidden large round at --cpus=2, and in local 600 s runs (classic 4.86M nodes, memo 15.4M nodes) they still did not certify. A per-book limit of 20 s gives them less than one round's cap.

## One fact wrong (CL-4)

Measured: fixed_file_order (one wrong data_quality row in H1) and missing_file_silent each fail one check and keep 105/108 (0.972). A program with one wrong figure in one hidden document loses only that document's check (3 or 5 of 108). Exactness is stated in instruction.md ("Each output document is graded whole on fresh books, and only an exact match counts.").

## Harden r2 cb8dada (1 Nov): measured on the final tests
Tests-only verifier (BUNDLE tests/test_output.py, reward.toml weight 1/108, no judge) in image cb8dada_verif built from tests/Dockerfile, `--memory 4g --cpus 2`, program first run on the shipped book, then `bash /tests/test.sh`. Logs `_runs/20261101/flood-repair-portfolio/harden2-20261101T1130/logs/ct_<p>.log`. The two sections above (baselines, runtime) were measured on the previous hidden seeds 714301/721402/731503 and are kept as history.

| program | shipped s | verifier s | tests (of 108) | lost | lever pts kept (of 78) |
|---|---|---|---|---|---|
| a1 paid-run program | 2.6 | 167.18 | 30 | H1-H3 21 checks + reruns_identical (TIMEOUT) | 0 |
| first-write (a1 step 11) | over 300 (killed) | 225.13 | 3 | everything except missing_input_is_named (TIMEOUT) | 0 |
| all-but-one (one BFS start) | 7.01 | 161.04 | 30 | H1-H3 + reruns_identical (TIMEOUT) | 0 |
| dae9563 | 12.56 | 191.80 | 30 | H1-H3 + reruns_identical (TIMEOUT) | 0 |
| elim (min-degree VE) | 0.86 | 161.72 | 83 | H1 7 checks (25); reruns of H1 passed, so a cap hit under verifier load | 53 |
| vebest (min-fill VE) | 1.33 | 150.16 | 108 | none | 78 (careful enumerator keeps the lever; recorded, not a blocker per route1 R5(d)) |
| oracle (harbor oracle x3, owner x1) | | 124.3 / 139.6 / 151.5; owner 125.2 | 108 | none | |

Lever share 78/108 = 72%; a1 program tests 30/108 = 27.78; timeout share of the a1 loss 100%. strong.py (per-round library) not run as a program: per-round linear sweep TIMEOUT at 60 s (h1_a1 KILL_TEST bench4).

## Harden r4 ea94780 (1 Nov): measured on the final tests
Docker --memory 4g --cpus 2, tests-only copy (exe_copy), shipped data in /app/data; log _runs/20261101/flood-repair-portfolio/harden4-20261101T2000/logs/verif_all.log. Reference busy (one core spinning) H1c-H3c 0.96-2.52 s, unbusy 1.19-3.42 s, limit 20 s.

| program | shipped s | verifier s | tests (of 108) | lost | lever pts kept (of 89) |
|---|---|---|---|---|---|
| oracle (solve.sh incl. self-checks) | 7.14 | 64.2 | 108 | 0 | 89 |
| a3 correct | 0.39 | 85.47 | 108 | 0 | 89 |
| a3 natural | 0.28 | 73.86 | 31 | 77 | 12 |
| a3 prefilter | 0.45 | 91.08 | 31 | 77 | 12 |
| a3 unchanged | 0.37 | 84.36 | 31 | 77 | 12 |
| a1 | 2.03 | 161.19 | 19 | 89 | 0 |
| all-but-one | 8.06 | 161.38 | 19 | 89 | 0 |
| first-write | 900.62 (killed) | 215.18 | 3 | 105 | 0 |
| fork probe | n/a | 242.33 | 0 | 108 | 0 |

Verifier worst measured 242.33 s (limit 2700, bar 2430). Harbor gate lanes: oracle 102.49 / 99.39 / 105.76 s, owner 101.22 s.

## Lessons for the master
- A secondary order lever whose wrong reading only moves data_quality rows is cheap to grade but stays far under the 25% bar | no change: secondary cap is 25% by design.
- LP rounding plus swaps was exact on some lattice rounds (h1_1, H3 R60496); two large rounds per book keep each book lost | no change: recorded in DESIGN and here.
