# BUILD REPORT: cleanroom-window-schedule (board 3040f47)

Status: DONE (BUILD READY). Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cleanroom-window-schedule/`. Session renamed (opencode ses_e8d2efcd2ffeDEglLpM8uaaTYq listed; codex no match). GEN fingerprint 160/160, QC 12/12, harness HEAD 5574d77e.

## Tree (22 files)
- environment/: Dockerfile, data/ (11 files: contract.md plus 10 inputs)
- solution/: solve.py (247 lines), solve.sh (copies solve.py, runs it, then a self-check stage that prints `check R1..R6 ok` and the rejected nights), TRUTH.md (8 sections)
- tests/: Dockerfile, test.sh, test_output.py (1278 lines, 30 checks), judge.toml (9 criteria), reward.toml (test_output 0.5/98, judge 0.5/24)
- instruction.md, task.toml (agent 7200 s uid 1000, verifier 2700 s)

## Data (21580 lines, 7 formats)
jobs.csv 3789, windows.tsv 3789, setup_fees.csv 2488, clients.jsonl 3000, regions.csv 2601, segments.tsv 3001, mandatory.json 1076, audit.toml 1663, bays.json 19, qualifications.ini 11, contract.md 143. Book: 415 nights (360 small, 25 medium, 15 large up to 72 jobs, 12 rejection plants including multi-defect nights, 3 empty). Chains: job -> client -> site -> region; job -> client -> segment; job -> night -> fee table; job -> night -> audit date order -> previous family; job -> window -> times.

## Levers (all rules in environment/data/contract.md, the single contract named once in instruction.md)
| lever | rule written at | wrong reading | tests kept | overall if all else right |
|---|---|---|---|---|
| LV-CW-1 exact max net | contract.md:89-91, coupling :97, limit :19-20 (2 s per night) | greedy 21/98, greedy+LS 24/98, raw exact and tuned raw (time out on dense/wide books) 48/98 | 21-48 | 0.557-0.695 |
| LV-CW-2 previous family across gaps, nights and initial | contract.md:68-73, :42, :55-56 | reset nightly 15, no initial 29, touching only 15 | 15-29 | 0.577-0.648 |
| LV-CW-3 shared crew with lead time (G-2) | contract.md:75-80 | no crew, naive collapse, lane by lane, flow relaxation 15 each | 15 | 0.577 |
There is no secondary lever. Check weight per lever: LV-CW-1 86/98, LV-CW-2 83/98, LV-CW-3 83/98 (LEVERS.md). Gates: each lever loses at least 51% of the tests, and the worst all-but-one overall score is 0.695, below 0.70 (COST_TABLE.md). If one fact is wrong in one hidden document, the program still keeps 93-95/98 (CL-4).

## Weights
Positive 98 over 28 checks, plus negatives -5 (reads /tests) and -3 (hardcoded shipped answers). Hidden books (dense, linked, wide; 25 points each, with feasibility, optimality and each rollup as separate checks): 75 (76.5%). Mutation (missing input named; relocated, reordered copy run twice): 6. Hidden plus mutated: 81 (82.7%). Shipped only: 17 (17.3%). Whole-document checks: 71/98 (72.4%). Isolated feasibility and optimality checks: 24/98 (24.5%). Plain-rule checks no lever fails: 15. Judge: 8 positive criteria worth 24 (R1-R6 conduct, R7 maintainability, R8 rejected-night list), plus R9 honesty -5. solve.py shares 6.3% of its lines with test_output.py.

## Results
- QC scripts: structure 17/0/0, instruction 5/0/0, tests 37/0/0, judge 19/0/0 (all PASS). Validator 41 passed, 0 failed, GATE PASS. VB 15.5 and DS-27 agree, so there is no OPEN CONFLICT Q18.
- Harbor 0.24 oracle: 1.0 / 1.0 / 1.0 (trials pdFMHnu, kZj4BpP, vokYLRF); nop 0.0. The verifier took 20.4-20.7 s of its 2700 s budget. The first oracle round scored 0.2041 because of a tests permission bug (the temp root was chmod'ed to 755, which blocked uid nobody). Fixed and re-run.
- Docker timing (pinned python:3.12-slim, 2 cpus): the reference's worst night is 0.38 s. Whole runs take 1.31 s for dense, 0.28 s for linked, 1.33 s for wide and 1.66 s for the shipped book. The raw-state exact optimiser and the tuned version with upper-bound pruning both exceed 20 s on dense and wide nights. Runtime therefore stays a lever component, and the H1/H3 densification step was not needed. Limit: 2 s x nights in the contract, TRUTH and the test timeout.
- RULE_COVERAGE: 44 rows, none at 0. EVIDENCE_MAP: 10 rows. Uniqueness: optimal-plan count is 1 on every accepted night (UNIQUENESS.md). Every hidden crew book has a naive-collapse crossing night, and check_exact.py enumerates 30 such shipped nights of at most 12 jobs.
- check_exact.py (independent of solve.py): all 9 documents are the same as the oracle's.
- Stacking: STACKING PASS (OUT/STACKING_CHECK.md). PRECHECK last line: `PRECHECK CLEAN`.
- Not run: the judged channel, P13 blind reads and the probe (master point 12).

## Open points
- G-3 vs G11: the tie order is stated (contract.md:91-95), but with a unique optimum a tie mutant fails no test. That order is noted in RULE_COVERAGE.md with no row.
- Master point 5 reading: a feasible plan's crew windows always fall in start order. Point 5 is therefore read as "the naive-collapse optimiser's plan for some night of each crew book has a later-starting job's window begin before an earlier one's". The build check asserts exactly this.

## Lessons for the master
- Local runners without root and setpriv miss uid-drop permission bugs | template_change: anubis kit run_tests note: always run the oracle through Harbor before ticking P4.
- macOS APFS hides case-sensitive path mutants | no change: rule mutants measured in Linux Docker.
- The validator demands negative_hardcoded_sample_answers, which needs a stated contract sentence | template_change: _COMMON_RULES_v3 add "contract states figures come from the files read".
- stacking_check.py TS-26 helper flags members on different books as double pay | no change: rebutted in STACKING_CHECK.md (a).
- Unique optima need lane asymmetry (distinct rates) plus a build-time redraw | no change: recorded in UNIQUENESS.md.
