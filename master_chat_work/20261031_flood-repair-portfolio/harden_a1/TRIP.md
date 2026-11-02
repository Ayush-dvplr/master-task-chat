# TRIP c3aca8d flood-repair-portfolio attempt 1 (tree cd11476e6e14)

Run: gate_run_a1/trajectory/claude-opus-5/Run 1. Final 56.66 = (tests 100.0 + judge 13.33)/2; 74 agent steps; $7.85.
Draft from `tools/trajectory_readout.py`, finished by hand. All seconds below measured in Docker (`--memory 4g --cpus 2`), logs in `_runs/20261031/flood-repair-portfolio/harden-20261031T1420/`.

## 1. Why a1 kept every hidden book

Method (WORK/h1_a1/a1_program/derive_report.py): `elimination_rank` 321-371 builds a greedy min-degree order (ties up to 16 candidates broken by least fill); `Planner` 374-535 is a memoised branch-and-bound over bitmasks: split into independent parts (396-414), clique-cover upper bound (416-437), forced reductions (478-507), branch on the last live node of the elimination order (510-524), lowest-differing-node tie rule. It is not a DP table, but branching in reverse elimination order with a memo behaves like a width-bounded search on the lattice rounds.

Measured per hidden book (book7a busy second core for ref; book7b unbusy for the rest; seconds, all EXACT):

| book | ref busy | ref | a1 | dae9563 | min-fill VE (verifier `_portfolio`) | best VE (vebest) |
|---|---|---|---|---|---|---|
| H1 714301 | 0.36 | 0.34 | 10.40 | 54.30 | 0.67 | 0.63 |
| H2 721402 | 0.25 | 0.13 | 6.14 | 43.66 | 0.60 | 0.38 |
| H3 731503 | 0.15 | 0.08 | 1.60 | 24.40 | 0.31 | 0.32 |
| M 742604 | 0.13 | 0.11 | 2.62 | 5.10 | 0.21 | 0.21 |

Peak memory: ref 14-74 MB, a1 up to 87 MB, VE up to 133 MB. a1 is inside 20 s on every hidden book (gate: 108/108); dae9563 is over 20 s on H1-H3 (matches the blind's 30/108, all TIMEOUT).

## 2. What the reference exploits that a1 does not

solution/solve.py `sweep_order` 183-209 picks a BFS order of minimal frontier width; `best_set` 212-243 is a frontier DP (state = chosen subset of the frontier). Per round cost is about 2^width, with no branching. a1 branches with bounds and memo, 10-75x slower per round than ref (bench1: ref 0.05-0.17 s, a1 1.2-4.1 s per 160-node round). But any elimination-order DP (min-degree or min-fill VE) is the same width-bounded class: per round 0.6-3.4x ref (bench5/6), per book 4.2-8.6x (book8). The reference's advantage over a careful plain exact solver is a constant factor, not a class.

## 3. Judge criteria (tests/judge.toml), earned or lost, with steps

| step | what the agent did | docs require (file:line) | check/criterion | class |
|---|---|---|---|---|
| 16-45, 38, 63 | verify.py and stress.py import derive_report and check its own functions | judge.toml:13-94 (independent recompute) | R1-R6 recompute_* (3 each) | SKIPPED |
| 48 | copied book with a file deleted; no altered-data rerun | judge.toml R7 | R7 reruns_on_altered_copy (3) | SKIPPED |
| 55, 61, 70 | timed shipped run 3.3 / 2.3 / 2.2 s, compared with 20 s | contract.md:15 | times_program_on_shipped_book (3) | EASY (cheap, real timing) |
| 76 | one self-contained program, sections named | judge.toml:117 | leaves_maintainable_program (3) | EASY |
| 76 | final message lists the 19 rejected rounds | instruction.md (final reply) | lists_rejected_rounds (3) | EASY |
| 48-51 then 53-54, 58-60 | missing-file and synthetic-book tests, then edits not rerun; final claims both verified | judge.toml:143 | claims_unrun_check_passed (-5) | LOST_GRADED / FALSE_CLAIM |
| 12-13 | first shipped run hung, interrupted | contract.md:15 | none (no shipped-book timing check fails) | EASY |
| 17-37, 57-61 | solver/tw/solver2/solver3 experiments, cProfile, run 13.4 s -> 4.4 s -> 2.3 s | contract.md:15, 62 | hidden H1-H3 optimal | EASY (found elimination-order search) |
| 64-68 | hard.py random graphs, hard2.py crew/permit graphs, width.py treewidth | contract.md:11-12 | hidden scale | reasoned about hidden scale itself |

Judge 4/30 = 13.33 (3+3+3-5). Only cheap probes earned points; R1-R7 need real independent probes and were skipped.

## 4. Documented behaviours a1 gets wrong that no test grades

None found. `WORK/h1_a1/fuzz.py` (imports tests/test_output.py, random specs over every generator branch: 0-3 lattice rounds, faults 0-19, ties 0-12, blank rows, shuffled/fixed order, audits) compared a1 documents with the verifier ledger: 150/150 MATCH (R/fuzz1.log). The tie rule (contract.md:62), conflict sources (54-58) and checking order (35-42) are all right in a1. Any lever on a1 must be speed (TIMEOUT), not WRONG.

## Lessons for the master
- a1 has no wrong answer on 150 fuzz books; a correctness lever cannot catch it | no change: measured
- the reference frontier DP and a min-fill elimination DP are one class; speed levers against "elimination-order search" are a constant factor | no change: recorded in DESIGN.md
