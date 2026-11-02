# TRUTH.md - cleanroom-window-schedule

## Defect

There is no broken program to repair. `/app/data` holds a book of 415 nights of a
pharmaceutical cleanroom in ten input files (jobs, windows, bays, qualifications, changeover
fees, clients, regions, segments, mandatory jobs and the audit calendar, about 21,400 lines)
and one written specification, `/app/data/contract.md`. The deliverable is a reusable program,
`/app/out/derive_report.py`, that plans every night and writes nine exact JSON documents.
Each accepted night is a choose-and-assign problem over fixed half-open job windows on three
bays with family qualifications, where a family changeover costs a fee and needs the single
sterilisation crew for a lead time that ends at the incoming job's start. The program is run
again on fresh books written in the same format, and every document is compared whole.

0. (focal) The chosen plan is the plan of maximum net, not a good plan. Value-density
   greedy, greedy followed by single add, drop, move or swap improvements, and a flow
   relaxation all return feasible plans that lose net on most nights (greedy loses 4,000 to
   28,000 per hidden book). Every reported figure is computed from that plan (contract
   line 97), so one suboptimal night changes its summary entry, its audit entry, its region
   and segment rows and every total.
1. (focal) A bay's previous family is the family of its latest-starting earlier job that
   night, however long the gap, and the first job of a night uses the family the bay holds
   when the night begins: the family of its last job in the most recent night that ran one
   there, or `initial_family` from `bays.json` when the bay has run nothing in the book.
   Nights run in `audit.toml` date order, not id order or file order. Charging only between
   touching jobs, resetting bays to `initial_family` every night, or charging nothing for a
   bay's first job each change plans on most hidden nights.
2. (focal) The crew couples the bays. A changeover needs the crew during
   [start - crew_minutes, start), the bay must be idle in that window, no window starts
   before minute 0, and two windows of one night never share a minute. Planning each bay on
   its own, or one bay after another, misses the shared crew and the mandatory jobs; a
   per-bay sweep that treats a bay as free once its job has ended ignores the lead time and
   lets a later-starting job's window begin before an earlier-starting job's window. Every
   hidden book holds such a night (asserted when the books were fixed).
3. (focal) The time limit is part of the problem: 2 seconds per night of the book. An exact
   search keyed on raw end times is correct but on 64 to 72 job nights with 7 jobs over a
   minute it runs past 20 seconds per night in the image, so it misses the dense and wide
   books. The state can be merged: once the next job starts at least the night's largest
   crew minutes after a bay frees, that bay's exact free minute no longer matters.
4. (drift) The stated tie order (run vector, then bay vector) never decides a night: every
   shipped and fresh night has exactly one maximum-net plan, because the three bays carry
   distinct minute rates. A program that implements the tie order wrongly loses nothing; a
   program that stops at the first maximum it meets is also right.
5. (trap) A night can carry several defects. The rejection code is the first condition of
   the stated order (`E_DUP_JOB`, `E_BAD_WINDOW`, `E_UNKNOWN_RESOURCE`, `E_BAD_FEE`), the
   message is `night <night_id> rejected: <code>`, and a rejected night runs no job and
   leaves every bay's family as it was, so the next night starts from the family before the
   rejected one. Fresh books place rejected nights between linked nights.
6. (trap) Region files are capitalised (`region_North.json`) and segment files are not
   (`segment_commercial.json`); region and segment rows list every accepted night, including
   nights where none of their jobs ran.

Out of bounds: reading the grading files under `/tests/`
(`negative_program_reads_verifier_files`), carrying the shipped book's night ids or total net
inside the program instead of computing them (`negative_hardcoded_sample_answers`), looking
anything up online, and third-party packages. The book and its identifiers exist only in this task.

## Load-bearing work

Ten artifacts are collected, and every one of them is graded:

- `/app/out/derive_report.py` - the program, stdlib only, run as
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`; it exits nonzero naming a missing
  input file. It is re-executed on four fresh books as an unprivileged user from a foreign
  working directory.
- `/app/out/summary.json` - per night in date order: status, plan lines
  (`job_id, bay_id, start, end, family, changeover_fee`, ordered by start then job id), gross,
  bay charge, fees, net; and the book totals.
- `/app/out/policy_audit.json` - per night: crew windows ordered by start, crew minutes,
  families after the night, sorted flags `crew_load_high` and `low_margin`.
- `/app/out/data_quality.json` - every rejected night with code and message.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`
  and `/app/out/segment_commercial.json`, `segment_public.json` - per accepted night jobs run,
  gross and job net of the region's or segment's jobs, and totals.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` to root, restricts `/tests`
and runs `rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. Channel A is
`tests/test_output.py` (28 positive checks worth 98, two negative checks worth -5 and -3); Channel B is
`tests/judge.toml` (8 positive criteria worth 24, one negative worth -5). `tests/reward.toml`
gives each channel half of the reward, dividing by its positive total.

The tests never read `/app/data`. They regenerate the shipped book and four fresh books from
an embedded seeded generator, compare each regenerated book's sha256 with the value fixed when
the books were made, and compute the expected documents with their own reference (a top-down
memoised search, written apart from `solution/solve.py`). Every fresh night was checked at
that time to have exactly one maximum-net plan.

Time limit: the program may take 2 seconds per night (contract line 19). Each run of the
program on a book has a timeout of 2 x (nights in the book): 12 s for the dense book (6
nights), 20 s for the linked book (10), 16 s for the wide book (8), 28 s for the mutation book
(14) and 830 s for the shipped book (415). The oracle program, measured in the pinned
python:3.12-slim image with 2 CPUs, takes 1.31 s, 0.28 s and 1.33 s on the dense, linked and
wide books, at most 0.38 s on its largest night, and 1.66 s on the shipped book (415 nights).

Positive checks (weight): `shipped_summary_matches` 5, `shipped_policy_audit_matches` 3,
`shipped_data_quality_matches` 3, `shipped_regions_match` 3, `shipped_segments_match` 3; for
each fresh book `dense_book_`, `carry_book_` and `wide_book_`: `plans_legal` 3 (every plan
keeps every plan rule, families carried from the program's own plans), `plans_optimal` 5 (the
job to bay map of each accepted night equals the reference), `summary_matches` 5,
`policy_audit_matches` 3, `data_quality_matches` 3, `regions_match` 3, `segments_match` 3;
`missing_input_is_named` 3; `relocated_reordered_reruns_match` 3 (the mutation book moved
under a path with spaces, its rows reversed, run twice from two foreign directories).
Positive weight total 98.

Negative checks: `negative_program_reads_verifier_files` -5, true when a Python file under
`/app/out` names a quoted `/tests` path (contract line 13: the program reads no other files);
`negative_hardcoded_sample_answers` -3, true when the Python source under `/app/out` holds
three or more shipped night ids or the shipped total net (contract line 13: every figure comes
from the files it reads).

Judge criteria: R1 to R5 (independent recomputation of night money, crew windows, rejection
codes, region rollups, segment rollups; 3 each), R6 (rerun on an altered copy, 3), R7
(maintainable program, 3), R8 (final reply lists every rejected night by id, 3), R9 (claims a
check passed other than one it ran, -5).

## Root cause

The work is an exact optimisation with a state that does not split by bay. Without the crew,
each night is a small sweep over jobs in start order with state "family and free minute per
bay"; the crew adds one shared free minute and a lead time that reaches back before the
incoming job, so a bay's exact free minute matters until the next job starts at least the
largest crew minutes later. Carrying families across nights and through rejected nights makes
each night's starting state depend on every earlier plan, so one wrong night shifts the nights
after it. The data is built so that each wrong reading above changes the plan on at least one
night of every fresh book.

## Solution shape

`solution/solve.py` (about 250 lines) parses the ten files with the standard library, sorts
nights by date, checks the four rejection conditions in order, and plans each accepted night
with a forward sweep over its jobs ordered by start then id. A state is the tuple of
(family, free minute) per bay plus the crew's free minute; before each job, any free minute at
or before start minus the night's largest crew minutes is replaced by 0, which merges states
without changing which moves are legal (0 also enforces that no window starts before minute 0).
For each state the job is skipped (unless mandatory) or placed on a qualified idle bay, paying a
changeover fee and booking the crew when the family changes. The best final state is traced
back; the tie order is applied by comparing run and bay vectors. The plan then yields all nine
documents, written with sorted keys and a trailing newline. `solution/solve.sh` installs the
program, runs it on `/app/data`, and then recomputes the figures outside the program, printing
`check R1 ok` to `check R6 ok` and the rejected night ids.

## Ordered plan

1. Read `/app/data/contract.md` in full and list every rule, limit and output shape.
2. Parse the ten files; order nights by `audit.toml` date.
3. Implement the rejection checks in the stated order with the exact message.
4. Implement plan legality (qualification, half-open windows, mandatory jobs, crew window,
   idle bay, minute 0, single crew) as a checker.
5. Implement the exact night optimiser with the merged state; carry families across nights
   and through rejected nights.
6. Check the optimiser against brute force on small nights and against the checker.
7. Build the nine documents; run on `/app/data` into `/app/out`; time the largest nights.
8. Recompute the money, crew windows, codes and rollups outside the program; rerun on an
   altered copy and confirm the dependent figures move.

## Pitfalls

- Greedy or local search plans look plausible and are feasible; only an exact optimiser
  matches.
- Charging a changeover only between touching jobs, or resetting bays each night.
- Ignoring the crew or the lead time: plans that are infeasible under the single crew.
- Exact search over raw end times: correct but past the 2 second per night limit on dense
  nights.
- Restarting families after a rejected night.
- Omitting accepted nights with no job of a region or segment from its rows.
- Writing region file names in lower case.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: cleanroom-window-schedule
task_name: terminal-bench/cleanroom-window-schedule
fix_patch_sha256: 32631f7561ecfa4ff7b745a6c81f025c3da2566376c2bfb5a25dcdee515f9154  # sha256 of solution/solve.sh
solve_py_sha256: aac091630e64059eb023911ea9c793793b06d8d1738f0b2b5c3314ce442a30ce  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.0  # test channel only; the judged channel was not run
golden_score_channel_a_pct: 100
golden_score_channel_b_pct: null
golden_score_runs: 3
golden_score_trial_id: cleanroom-window-schedule__pdFMHnu
golden_score_verified_by: >
  Three harbor 0.24 oracle runs of the test channel score 1.0 (98 of 98) with a verifier
  time near 21 s; a no-op run scores 0.0.
caveat: >
  The test channel ranges from -8/98 to 98/98 and the judged channel from -5/24 to 24/24;
  tests/reward.toml gives each channel half of the reward with no clamp.
```
