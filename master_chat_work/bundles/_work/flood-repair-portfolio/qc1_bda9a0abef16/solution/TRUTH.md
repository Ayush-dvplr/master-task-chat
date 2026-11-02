# TRUTH.md - flood-repair-portfolio

## Defect

There is no broken program to repair. `/app/data` holds a book of 192 funding rounds of a
flood repair programme in nine data files (proposals, segment codes, sites, region codes,
crews, permits, exclusions, benefit tables and audit queries, about 21,200 lines), a
`manifest.json`, and one written specification, `/app/data/contract.md`. The deliverable is a
reusable program, `/app/out/derive_report.py`, that checks, values and plans every round and
writes ten exact JSON documents. Each planned round is a maximum-weight independent set
problem: choose the conflict-free set of proposals with the greatest total benefit, with a
stated tie-break. The program is run again on fresh books written in the same format, and
every document is compared whole.

0. (focal) The chosen portfolio is the portfolio of greatest total benefit, not a good
   portfolio. Each book carries two large rounds (144 to 160 proposals, each in conflict with
   about 4.8 others) whose conflicts form a planar near-lattice with odd holes and near-equal
   benefits. Greedy by benefit or by benefit per conflict, greedy followed by one-for-many and
   two-for-many swaps, iterated local search for 10 seconds, and linear relaxation with
   rounding (with and without swaps) all return feasible portfolios that fall short on these
   rounds, by 44 to 14,160 benefit units. Branch and bound with colouring bounds, and memoised
   search with degree, domination and simplicial reductions and component split, do not
   certify one large round within 20 seconds. Every reported figure comes from the chosen
   portfolio (contract line 64), so one wrong large round changes its summary entry, its
   audit rows, its region and segment rows and the totals.
1. (focal) The fast exact route is found from the instance. Ordering the proposals of a large
   round by a breadth-first sweep from a far proposal keeps at most 11 to 13 proposals "open"
   (placed, with a conflicting proposal still to come), and a sweep over the independent
   subsets of that frontier, or a variable elimination along a min-fill order, finishes a large
   round in about 0.1 seconds. Searching in id order or file order does not, because ids and
   row order are independent of the conflict structure.
2. (focal) Conflicts come from three files and each is load-bearing. An exclusive crew joins
   its proposals, a shared crew joins nothing; a permit joins proposals attached to it by
   `held` or `applied` rows of that round, a `withdrawn` row counts for nothing, and a permit
   id seen in another round is a different permit; an exclusion entry may name a site, which
   stands for every proposal of that round at that site. In each large round crews carry about
   22%, site-named exclusions about 16% and permits about 36% of the conflicts. Dropping any
   one source, or reading withdrawn rows as held, changes the chosen portfolio.
3. (focal) Benefit is `households * (segment rate + risk uplift) + site premium` with the risk
   class taken from `risk_override` when it is not empty, else from the site (contract
   line 23). About a quarter of proposals carry an override that differs from the site class;
   one risk class has a negative uplift, so some proposals are valued below their premium.
4. (drift) `held` and `applied` permit rows act the same; only `withdrawn` differs. The
   conflict record limit (900 per round) is never approached; large rounds carry 430 to 490.
5. (trap) Ties decide portfolios on small rounds: twin proposals of equal benefit that
   conflict, and three-proposal paths whose middle benefit equals the sum of its ends. The rule
   compares sorted id lists at the first differing position; taking the first maximum found, or
   preferring the larger id, changes these rounds.
6. (trap) A round can carry several faults. The reported fault is the first faulty row found by
   taking the round-scoped files in the manifest's declared order (fresh books shuffle it),
   rows in file order, and checks in the listed order; row numbers count data rows of the
   whole file from 1; `NONPOSITIVE_BENEFIT` is tested only when no file fault exists.

Out of bounds: reading the grading files under `/tests/`
(`negative_program_reads_verifier_files`), carrying the shipped answers in the program
(`negative_hardcoded_sample_answers`), looking anything up online, and third-party
packages (the program is run with `python3 -I -S`, so an installed package is unreachable).
The book and its identifiers exist only in this task.

## Load-bearing work

Eleven artifacts are collected and every one is graded:

- `/app/out/derive_report.py` - the program, one self-contained stdlib file, run as
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`; it exits 1 with
  `ERROR MISSING_FILE <name>` when a declared file is missing. It is re-executed on three fresh
  books, one mutation book and two altered copies of it as an unprivileged user from a foreign
  working directory.
- `/app/out/summary.json` - per round in id order: status, proposal rows, selected ids, total
  benefit; book counts and totals.
- `/app/out/policy_audit.json` - one row per audit query: VALUE rows with the valuation terms
  and whether the proposal was selected, PAIR rows with the conflict sources and the selection
  of both proposals.
- `/app/out/data_quality.json` - every rejected round with code, file and row; conflict pair
  counts by source; withdrawn permit rows.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`
  and `/app/out/segment_commercial.json`, `segment_public.json` - per planned round the
  selected proposals of that region or segment and their benefit, and totals.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier` to root, restricts `/tests`
and runs `rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. Channel A is
`tests/test_output.py` (32 positive checks worth 108, two negative checks worth -5 and -3); Channel B
is `tests/judge.toml` (10 positive criteria worth 30, one negative worth -5).
`tests/reward.toml` gives each channel half of the reward, dividing by its positive total.

The tests never read `/app/data`. They regenerate the shipped book, three fresh books and one
mutation book from an embedded seeded generator, compare each regenerated book's sha256 with
the value fixed when the books were made, and compute the expected documents with their own
reference (a min-fill variable elimination, written apart from `solution/solve.py`). Every
large round of every book has exactly one maximum-benefit portfolio; each planted tie round
has exactly two.

Time limit: 20 seconds of wall time per book (contract line 15); each run of the program has a
timeout of 20 s. The oracle program in the pinned python:3.12-slim image takes 0.16 to 0.25 s
on the shipped book and 0.08 to 0.12 s on each fresh book, with 1 or 2 CPUs.

Positive checks (weight): `artifacts_present` 1; `shipped_summary_matches`,
`shipped_policy_audit_matches`, `shipped_data_quality_matches`, `shipped_regions_match`,
`shipped_segments_match` 3 each; for each fresh book `h1_book_`, `h2_book_`, `h3_book_`:
`feasible` 3 (every selected set is conflict-free and maximal under the reference conflicts),
`optimal` 5 (selected ids of every planned round equal the reference), `summary` 5,
`policy_audit` 3, `data_quality` 3, `regions` 3, `segments` 3;
`scaled_shuffled_summary_matches` 5 (mutation book with segment rates scaled by 1.37 and rows
shuffled); `rotated_summary_matches` 3; `relocated_copy_matches` 3 (path with spaces);
`missing_input_is_named` 3; `reruns_identical` 3. Positive weight total 108.

Negative checks: `negative_program_reads_verifier_files` -5, true when a Python file under
`/app/out` names a quoted `/tests` path; `negative_hardcoded_sample_answers` -3, true when a
Python file under `/app/out` holds three or more selected proposal ids of the shipped book or
its total benefit (contract line 5: the program reads the book in `DATA_DIR`).

Judge criteria: R1 to R6 (independent recomputation of benefits, pair sources, rejection
codes, region rollups, segment rollups, and the portfolios of rounds of at most 16 proposals by
enumeration; 3 each), R7 (rerun on an altered copy, 3), R8 (times the program against the
20 second limit, 3), R9 (maintainable program, 3), R10 (final reply lists every rejected round
by id, 3), R11 (claims a check passed other than one it ran, -5).

## Root cause

The work is an exact optimisation over a conflict graph that has to be assembled from three
files and valued from three more. Maximum-weight independent set is hard in general, and the
large rounds are built so that the reflex methods (greedy, swaps, relaxation, generic branch
and bound) either fall short or run out of time, while the graph has a narrow frontier along a
breadth-first order that a sweep or elimination exploits. The near-equal benefits make many
portfolios almost tie, so a slip in valuation or in one conflict source moves the optimum.
Because every document is computed from the chosen portfolio, one wrong round changes every
document family of its book.

## Solution shape

`solution/solve.py` (about 360 lines) reads the manifest and the nine files with the standard
library, groups rows by round, checks faults in declared file order, values each proposal,
derives conflict pairs with their sources, and plans each planned round. Planning splits the
round into connected parts; for each part it picks a breadth-first order from several start
proposals (a far proposal and low-degree ones) with the smallest frontier, and sweeps along it
keeping, for every independent subset of the frontier, the best partial portfolio. The
tie-break is folded into the weights: each benefit is multiplied by 2^n and the proposal of
rank r in ascending id order adds 2^(n-1-r), so the single maximum of the scaled weights is the
maximum-benefit portfolio with the smallest sorted id list. The documents are written with
two-space indentation and a trailing newline. `solution/solve.sh` installs the program, runs
it on `/app/data`, then recomputes figures outside the program and prints `check R1 ok` to
`check R8 ok` and the rejected round ids.

## Ordered plan

1. Read `/app/data/contract.md` in full and list every rule, limit and output shape.
2. Parse the manifest and the nine files; group rows by round.
3. Implement the fault checks in declared file order, rows in file order, checks in listed
   order, with whole-file row numbers; then `NONPOSITIVE_BENEFIT`.
4. Value proposals with the override precedence.
5. Derive conflicts from exclusive crews, non-withdrawn permit rows within the round, and
   exclusions with site names expanded.
6. Implement an exact planner; check it against brute force on small rounds; time it on the
   two large rounds of the shipped book and keep it far inside 20 seconds.
7. Apply the tie-break and build the ten documents from the chosen portfolios.
8. Recompute benefits, pair sources, codes and rollups outside the program; rerun on an
   altered copy and confirm the dependent figures move.

## Pitfalls

- Greedy, swap and relaxation portfolios are feasible and look plausible; only an exact
  planner matches on the large rounds.
- Generic branch and bound or memoised search in id order times out on the large rounds.
- Counting shared crews, withdrawn permit rows, or a permit id across rounds as conflicts;
  ignoring site names in exclusions.
- Using the site's risk class when an override is present; forgetting the premium.
- Taking files in fixed order instead of the manifest's declared order; numbering rows within
  the round instead of the whole file.
- Breaking ties by the first maximum found or by the larger id.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: flood-repair-portfolio
task_name: terminal-bench/flood-repair-portfolio
fix_patch_sha256: 6c1b865f8ee9d4fb2b92ce8009028a2d702c34be63de31c548838924650fb4e0  # sha256 of solution/solve.sh
solve_py_sha256: 4191f4c1deaff1e05fc7df285239bf53eed9aa83beeb1ce8864e1a69c9e7d47c  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.0  # test channel only; the judged channel was not run
golden_score_channel_a_pct: 100
golden_score_channel_b_pct: null
golden_score_runs: 3
golden_score_trial_id: flood-repair-portfolio__j89Z7bE
golden_score_verified_by: >
  Three harbor 0.24 oracle runs of the test channel score 1.0 (108 of 108) with a
  verifier time of 21 to 24 seconds; a no-op run scores 0.0.
caveat: >
  The test channel ranges from -8/108 to 108/108 and the judged channel from -5/30 to
  30/30; tests/reward.toml gives each channel half of the reward with no clamp.
```
