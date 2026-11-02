# LEVERS flood-repair-portfolio

One row per check of tests/test_output.py. A lever id is listed when at least one wrong program for that lever (WORK/mutants/*.py lever rows, WORK/rule_mut/*.py stated-rule rows) fails the check. "stated" = a stated output-format or fault-reporting rule outside the four levers.

| check | weight | levers |
|---|---|---|
| artifacts_present | 1 | LV-FP-2, LV-FP-4, stated |
| shipped_summary_matches | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| shipped_policy_audit_matches | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| shipped_data_quality_matches | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| shipped_regions_match | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| shipped_segments_match | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h1_book_feasible | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h1_book_optimal | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h1_book_summary | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h1_book_policy_audit | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h1_book_data_quality | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h1_book_regions | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h1_book_segments | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h2_book_feasible | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h2_book_optimal | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h2_book_summary | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h2_book_policy_audit | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h2_book_data_quality | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h2_book_regions | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h2_book_segments | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h3_book_feasible | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h3_book_optimal | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h3_book_summary | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h3_book_policy_audit | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h3_book_data_quality | 3 | LV-FP-2, LV-FP-3, LV-FP-4, stated |
| h3_book_regions | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| h3_book_segments | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| scaled_shuffled_summary_matches | 5 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| rotated_summary_matches | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, stated |
| relocated_copy_matches | 3 | LV-FP-1, LV-FP-2, LV-FP-3, LV-FP-4, coupling, stated |
| missing_input_is_named | 3 | LV-FP-4, stated |
| reruns_identical | 3 | LV-FP-1, LV-FP-2, LV-FP-4, stated |
| negative_program_reads_verifier_files | -5 | G4 cheat act |
| negative_hardcoded_sample_answers | -3 | G4 cheat act |

| lever | positive weight of checks it can fail | share of 108 |
|---|---|---|
| LV-FP-1 | 83 | 77% |
| LV-FP-2 | 105 | 97% |
| LV-FP-3 | 101 | 94% |
| LV-FP-4 | 108 | 100% |
| coupling | 27 | 25% |
| stated | 108 | 100% |

Negative checks: negative_program_reads_verifier_files -5, negative_hardcoded_sample_answers -3 (two distinct acts, AL-28).

## Harden r2 cb8dada (1 Nov): LV-FP-1 at stated scale (time-out lever)
Hidden books H1, H2, H3 now hold 100 rounds each, 60 of them large lattice rounds (the old two-round large list repeated 30 times; seeds 815301, 822402, 833503; hidden_meta.json candidate `h2_rep30`). Sizes stay inside contract.md:11-12; the limit stays contract.md:15 (20 s). A program whose exact search is fast on the shipped book's two large rounds but grows steeply per round runs past 20 s on each hidden book and loses all of that book's checks; reruns_identical runs H1 twice more.

| program (Docker, 2 cpus, 4 GiB) | H1 / H2 / H3 seconds | verdict | lever points kept of 78 |
|---|---|---|---|
| reference solve.py, both cores busy | 1.12 / 1.11 / 0.95 | EXACT | 78 |
| a1 paid-run program | >60 / >60 / >60 | TIMEOUT | 0 |
| first-write (a1 step 11) | >40 (rep20) x3 | TIMEOUT | 0 |
| all-but-one (ref, single BFS start) | 42.86 / 54.89 / 42.46 | TIMEOUT | 0 |
| dae9563 program | >40 (rep20) x3 | TIMEOUT | 0 |
| elim_program (careful min-degree VE) | 7.93 / 7.55 / 6.51 | EXACT | 78 |
| vebest_program (careful min-fill VE) | 6.86 / 6.51 / 5.93 | EXACT | 78 |
| strong.py (linear sweep, per round) | >60 per large round | TIMEOUT | 0 |

Lever points: 3 books x 25 (feasible 3, optimal 5, summary 5, policy_audit 3, data_quality 3, regions 3, segments 3) + reruns_identical 3 = 78 of 108 positive (72%). Every lost point is a time-out (timeout share 100%, Ayush flood time-out exception 31 Oct 11:45). Lever 2 (wrong kind): none found (a1 program skips self pairs L270-272, dedups permit members L294-295; ids fixed width; fuzz 150/150 MATCH).

## Harden r4 ea94780 (1 Nov): shared-crew limit (LV-CAP), measured on the final tests
New documented rule at environment/data/contract.md:62: "A crew whose mode is `shared` can work on at most four of the proposals in a portfolio." Hidden books H1, H2, H3 carry 3 capped rounds each and M carries 2 (tests/test_output.py `_capped_round` L647, `make_book` L791, own RNG seed*31+7177); shipped answers unchanged (round R62233, crew C2534, four proposals, all chosen). `_feasible` L1480-1510 now checks the limit and exempts from maximality a proposal whose shared crew already has four picks.

LV-CAP lever points: H1-H3 x 25 (feasible 3, optimal 5, summary 5, policy_audit 3, data_quality 3, regions 3, segments 3) + scaled 5 + rotated 3 + relocated 3 (book M) = 86; with the timeout lever (reruns_identical 3) the union is 89 of 108 positive (82.4%). data_quality is selection independent, so a wrong-selection program keeps 3 per H book.

| program | verifier s | tests (of 108) | lever pts kept (of 89) | verdict on capped rounds |
|---|---|---|---|---|
| oracle (solve.sh) | 64.2 | 108 | 89 | EXACT |
| a3 correct (enumerate keep sets, re-solve) | 85.47 | 108 | 89 | EXACT |
| a3 natural (post-step: ban least-benefit member, re-solve) | 73.86 | 31 | 12 | WRONG |
| a3 prefilter (keep top four by benefit) | 91.08 | 31 | 12 | WRONG |
| a3 unchanged | 84.36 | 31 | 12 | WRONG |
| a1 program | 161.19 | 19 | 0 | TIMEOUT H1-H3, WRONG M |
| all-but-one | 161.38 | 19 | 0 | TIMEOUT/WRONG |
| first-write | 215.18 | 3 | 0 | TIMEOUT |
| fork probe | 242.33 | 0 | 0 | survivors 0 |

Natural a3 loses 77 of 89 lever points by WRONG (86.5%). Log: _runs/20261101/flood-repair-portfolio/harden4-20261101T2000/logs/verif_all.log.

## Harden r6 ea04435: Budget A+B Crowd Rounds
Kind (c), measured scale/budget lever. In tests/test_output.py, make_book replaces large-round indices 0,10,20,30,40,50 after generating the ordinary rounds, faults, audits and capped rounds. Its own RNG (_Rng(seed*37+9011)) builds 150 lattice proposals plus ten isolated members of a new shared crew. Each replacement has 160 proposals; the original stream has already drawn all old rounds. H1-H3 alone opt in; SHIPPED/M/MS/MR file and expected-document digests are unchanged.

P's capped_dp enumerates C(10,6)=210 drops, below COMBO_CAP=256, but re-solves the lattice per combination. Its four-second round deadline sends choose() to greedy (paid program lines 355-356), then its thirteen-second book budget starves later rounds. The independent verifier's _capped exhausts the choices without that fallback. The reference splits disconnected parts and stays exact. Named witness copied to r6_build/witness; final-book measurements are in r6b-20261102T2018/scratch/results_H1.json, results_H2.json and results_H3.json.

The lever targets the existing optimal 5, summary 5, policy_audit 3, regions 3 and segments 3 checks per H book: 19 x 3 = 57/108 positive points (52.78%). Feasible 3 and data_quality 3 per book can remain correct. No test body, registration or test weight was changed. reruns_identical remains a separate determinism check and may also fail when a budget-dependent program returns different outputs.
