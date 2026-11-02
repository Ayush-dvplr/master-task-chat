# DESIGN_SUMMARY 3040f47 cleanroom-window-schedule (full: WORK/DESIGN.md)
Core under G-2: book of nights; jobs with fixed [start,end) minutes; 3 bays (qualified families, minute
rate); mandatory jobs. Changeover when family differs from the bay's previous family: fee + a window of
crew_minutes ending at the job start, worked by ONE shared crew (windows disjoint across bays, bay idle,
start >= 0). Previous family = last job the bay ran in the book (date order); initial family before.
Maximise value - bay charge - fees per night; coupling sentence verbatim in the contract.
G-2 evidence: without crew, joint per-bay-state sweep DP is exact and < 0.4 s (core too easy).
Reference: sweep DP with lead-time state collapse, 0.05-0.33 s per 72-job night (local; Docker in P4).
Stated limit 10 s per night (>= 3x oracle; reference <= 1/4).

Levers: LV-CW-1 exact optimum; LV-CW-2 previous family across gaps/nights + initial; LV-CW-3 shared crew
with lead time. No secondary lever.

Baseline results per hidden book, 3 seeds (nights differing / infeasible / net loss):
| book (nights, jobs) | greedy | greedy+LS | lane-by-lane | flow relax | reset nightly | no initial | no crew | naive collapse |
| H1 dense (5, 64-72) | 5/5, 1, 6.4k-15.8k | 5/5, 1, 3.8k-14.0k | 5/5 inf | 3-5/5 | 3-4/5 | 1-5/5 | 3-4/5 | 4-5/5 |
| H2 carry (8, 20-48) | 8/8, 0-1, 7.9k-17.8k | 8/8, 0-1, 7.1k-14.4k | 7-8/8 inf | 3-7/8 | 5/8 | 3-6/8 | 2-3/8 | 4-8/8 |
| H3 wide (6, 48-72) | 6/6, 0-2, 4.0k-28.0k | 6/6, 0-2, 4.0k-23.9k | 5-6/6 inf | 6/6 | 3-4/6 | 3-5/6 | 4/6 | 6/6 |
Every baseline fails every hidden book (whole-doc per book), G-4 met on all 3 seeds surveyed.

Optimum uniqueness: optimal-plan count 1 on 54/57 surveyed hidden nights; 1 night count 2, 2 nights
count 0 (mandatory infeasible). Generator redraws any night with count != 1 and asserts it (G-3).

Tests (weights 5/3/1): visible shipped book 5 docs (17); hidden 3 books x {feasible 3, optimal 5,
summary 5, policy 3, data_quality 3, regions 3, segments 3} (75, share ~78%); mutation: missing source
named (3), rerun identical (3); negative /tests/ read (-5). About 28 tests. Feasibility, optimality,
rollups are separate tests per book.
Projected cost table (real wrong programs in P4): LV-CW-1 alone ~85%, LV-CW-2 ~75%, LV-CW-3 ~90% of test
weight; all-but-one overall < 70 in each case.
Judge: 8-10 criteria (J2 x5 recompute per output family, J3 honesty -3, J4 maintainability, J6 rejected
nights by id, J9 altered copy).
Risks: LV-CW-2 readable as a one-line rule (kept defined, not emphasised; date order only in audit.toml);
verifier runtime (measure in Docker); TS-S13 overlap (tests use a different exact formulation).
OPEN CONFLICT: none yet (Q18 reserved for DS-27 vs VB 15.5 at P7).
