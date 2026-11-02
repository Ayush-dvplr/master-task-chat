# COST_TABLE: cleanroom-window-schedule

Every row is a real wrong program (WORK/mutants/<name>.py, built from solution/solve.py) run through the full test file by WORK/run_tests.py. Tests positive total 98. Overall = 0.5 x tests share + 0.5 x judge share, judge share assumed 0.90.
Non-raw mutants were measured at 4 s per night and are fast, so the stated 2 s limit does not change them; the raw optimisers were re-measured at 2 s per night (tmp/cost2).

## Each lever wrong alone

| lever | wrong program | tests kept | tests lost | checks failed | overall |
|---|---|---|---|---|---|
| LV-CW-1 exact max net plan | greedy (value density, mandatory first) | 21/98 | 79% | 21 | 0.557 |
| LV-CW-1 | greedy_ls (greedy + single add/remove/move/swap search) | 24/98 | 76% | 20 | 0.572 |
| LV-CW-1 | raw_exact (exact, state keyed on raw end times, master ii) | 48/98 | 51% | 14 | 0.695 |
| LV-CW-1 | raw_tuned (raw state + canonical memo + upper-bound pruning, master iii) | 48/98 | 51% | 14 | 0.695 |
| LV-CW-2 carried previous family | reset_nightly (bays reset to initial family every night) | 15/98 | 85% | 23 | 0.577 |
| LV-CW-2 | no_initial (first job on a bay never charged) | 29/98 | 70% | 19 | 0.648 |
| LV-CW-2 | touching_only (charge only when previous job ends at start) | 15/98 | 85% | 23 | 0.577 |
| LV-CW-3 shared crew + lead time | no_crew (crew windows may overlap) | 15/98 | 85% | 23 | 0.577 |
| LV-CW-3 | naive_collapse (bay free once its job ends, lead time ignored) | 15/98 | 85% | 23 | 0.577 |
| LV-CW-3 | lane_by_lane (natural per-bay DP, one bay after another) | 15/98 | 85% | 23 | 0.577 |
| LV-CW-3 | flow_relax (ignore crew and qualifications) | 15/98 | 85% | 23 | 0.577 |

Gate: each lever alone loses at least 25% of tests: met (smallest loss 51%, raw optimisers).
Gate: all but one lever right, overall below 0.70: met for every lever; worst case 0.695 (LV-CW-1 via raw_tuned).
No negative check fired on any mutant.

## All but this lever right (worst wrong program per lever, rubric 0.90)

| lever wrong | predicted overall |
|---|---|
| LV-CW-1 | 0.695 (raw_tuned); greedy family 0.557 to 0.572 |
| LV-CW-2 | 0.648 (no_initial) |
| LV-CW-3 | 0.577 |

## Runtime of exact optimisers in Docker (master point 2)

Pinned python:3.12-slim image, --cpus 2 --memory 4g, cap 20 s per night (WORK/timing.py, tmp/dock/timing.log).

| program | dense book (6 nights, budget 12 s) | linked book (10 nights, budget 20 s) | wide book (8 nights, budget 16 s) |
|---|---|---|---|
| reference solution/solve.py | worst night 0.38 s, book 1.31 s | worst 0.04 s, book 0.28 s | worst 0.27 s, book 1.33 s |
| (ii) raw_exact | first night over 20 s, book killed at 70.8 s | worst 3.66 s, book 12.4 s | night over 20 s, book killed at 128.9 s |
| (iii) raw_tuned | first night over 20 s, book killed at 53.5 s | worst 1.20 s, book 4.0 s | nights 12.9 s, 6.9 s, over 20 s, book killed at 140.6 s |

The tuned raw optimiser does not finish the dense or wide book in budget, so runtime is part of LV-CW-1 and the H1/H3 densification step was not needed. Stated limit 2 s per night = smallest whole seconds keeping the reference's largest night (0.38 s) at or below one quarter of it. Oracle on the shipped book (415 nights) in Docker: 1.66 s against a budget of 830 s.

## One fact wrong (CL-4)

A program with one wrong figure in one hidden document loses only that document's check (3 or 5 of 98), so it keeps 93 to 95 of 98. Exactness is stated in instruction.md ("only an exact match counts").

## Lessons for the master
- Raw-state exact optimisers are the lenient case for LV-CW-1 (0.695); a budget formula per night keeps them just under 0.70 | no change: recorded here and in BUILD_REPORT.
- Linked mid-size book is solvable by raw search in budget, so dense and wide books carry the runtime share | no change: by design.
