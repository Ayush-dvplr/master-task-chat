# TRUTH.md - flood-repair-portfolio

## Defect

There is no broken program to repair. `/app/data` holds a book of 192 funding rounds of a
flood repair programme in nine data files (proposals, segment codes, sites, region codes,
crews, permits, exclusions, benefit tables and audit queries, about 21,200 lines), a
`manifest.json`, and one written specification, `/app/data/contract.md`. The deliverable is a
reusable program, `/app/out/derive_report.py`, that checks, values and plans every round and
writes nine exact JSON documents. Each planned round is a maximum-weight independent set
problem: choose the conflict-free set of proposals with the greatest total benefit in which
no crew of mode `shared` works on more than four proposals (contract line 62), with a
stated tie-break. The program is run again on fresh books written in the same format, and
every document is compared whole.

0. (focal) The chosen portfolio is the portfolio of greatest total benefit, not a good
   portfolio. The shipped book carries two large rounds and each fresh book sixty among its
   103 rounds (144 to 160 proposals, each in conflict with 4.7 to 5.0 others); their conflicts
   form a planar near-lattice with odd holes and near-equal benefits. Greedy by benefit or by
   benefit per conflict, greedy followed by one-for-many and
   two-for-many swaps, iterated local search for 10 seconds, and linear relaxation with
   rounding (with and without swaps) all return feasible portfolios that fall short on these
   rounds. Branch and bound with colouring bounds, and memoised
   search with degree, domination and simplicial reductions and component split, do not
   certify one large round within 20 seconds. Every reported figure comes from the chosen
   portfolio (contract line 64), so one wrong large round changes its summary entry, its
   audit rows, its region and segment rows and the totals.
1. (focal) The fast exact route is found from the instance. Ordering the proposals of a large
   round by a breadth-first sweep from a far proposal keeps at most 11 to 13 proposals "open"
   (placed, with a conflicting proposal still to come), and a sweep over the independent
   subsets of that frontier finishes a large round in about 0.02 seconds and a fresh book in
   about a few seconds; a variable elimination along a min-fill order takes several seconds a fresh
   book, and a search that needs a second or more per large round exceeds the 20 second limit
   on a fresh book. Searching in id order or file order does not, because ids and
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
4. (focal) A crew of mode `shared` joins no pair of proposals, yet a portfolio holds at most
   four of its proposals (contract line 62). Each fresh book carries three rounds, and the
   mutation book two, in which one shared crew has six to eight proposals laid out in two or
   more chains of one to four of them, each two neighbours in a chain joined through one
   proposal of an exclusive crew by two exclusion entries; without the limit the greatest
   portfolio takes six or more of that crew's proposals. On every such round the greatest
   total under the limit is reached by one portfolio only, every proposal of the crew it
   leaves out conflicts with a proposal it takes, and it differs from keeping the four
   highest benefits or the four smallest ids before planning, from dropping the
   lowest-benefit pick after planning (with or without planning again), from keeping the
   four highest-benefit picks and planning again, from removing the pick whose loss is
   least one at a time, and from applying the limit in each connected part alone. The
   shipped book has one round (R62233) in which a shared crew (C2534) has four proposals,
   all chosen, and none with more, so its answers are the same with or without the limit.
+   Each fresh book also carries six 160-proposal crowd rounds with ten isolated members
+   of a shared crew. The exact route separates their independent lattice component.
5. (drift) `held` and `applied` permit rows act the same; only `withdrawn` differs. The
   conflict record limit (900 per round) is never approached; large rounds carry 425 to 517.
6. (trap) Ties decide portfolios on small rounds: twin proposals of equal benefit that
   conflict, and three-proposal paths whose middle benefit equals the sum of its ends. The rule
   compares sorted id lists at the first differing position; taking the first maximum found, or
   preferring the larger id, changes these rounds.
7. (trap) A round can carry several faults. The reported fault is the first faulty row found by
   taking the round-scoped files in the manifest's declared order (fresh books shuffle it),
   rows in file order, and checks in the listed order; row numbers count data rows of the
   whole file from 1, and an empty line is not a data row (each fresh book carries one inside
   `proposals.csv` and `permits.csv`, ahead of faulty rows); `NONPOSITIVE_BENEFIT` is tested only
   when no file fault exists.

Out of bounds: reading the grading files under `/tests/`
(`negative_program_reads_verifier_files`), carrying the shipped answers in the program
(`negative_hardcoded_sample_answers`), looking anything up online, and third-party
packages (the program is run with `python3 -I -S`, so an installed package is unreachable).
The book and its identifiers exist only in this task.

## Load-bearing work

Ten artifacts are collected and every one is graded:

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
is `tests/judge.toml` (13 positive criteria worth 41, two negatives worth -5 each).
`tests/reward.toml` gives each channel half of the reward, dividing by its positive total.

The tests never read `/app/data`. They regenerate the shipped book, three fresh books and one
mutation book from an embedded seeded generator, compare each regenerated book's sha256 with
the value fixed when the books were made, and compute the expected documents with their own
reference (a min-fill variable elimination, written apart from `solution/solve.py`, run
once for every choice of four proposals of each shared crew that has more than four in the
round). Six large rounds per fresh book have 150 lattice proposals and ten isolated
members of a new shared crew. Their generator uses a separate RNG stream after all
ordinary round draws; shipped and mutation books remain byte-identical. The isolated
members expose repeated exact work across the 210 ways to drop six of ten members.
Every run starts in its own session, and the whole group is killed when it ends.

Time limit: 20 seconds of wall time per book (contract line 15). Each submitted run
has a timeout of 20 s. In the r6 re-measure, the reference took 1.5842 s on H1 and
1.9030 s with a CPU burner. The three-book and full-verifier evidence is recorded in
the harden_r6 report; historical timings are not current gate evidence.

Positive checks (weight): `artifacts_present` 1; `shipped_summary_matches`,
`shipped_policy_audit_matches`, `shipped_data_quality_matches`, `shipped_regions_match`,
`shipped_segments_match` 3 each; for each fresh book `h1_book_`, `h2_book_`, `h3_book_`:
`feasible` 3 (every selected set is conflict-free, gives no shared crew more than four
proposals, and is maximal under the reference conflicts except for proposals of a shared
crew that already has four),
`optimal` 5 (selected ids of every planned round equal the reference), `summary` 5,
`policy_audit` 3, `data_quality` 3, `regions` 3, `segments` 3;
`scaled_shuffled_summary_matches` 5 (mutation book with segment rates scaled by 1.37 and rows
shuffled); `rotated_summary_matches` 3; `relocated_copy_matches` 3 (path with spaces);
`missing_input_is_named` 3; `reruns_identical` 3. Positive weight total 108.

Negative checks: `negative_program_reads_verifier_files` -5, true when a Python file under
`/app/out` names a quoted `/tests` path; `negative_hardcoded_sample_answers` -3, true when a
Python file under `/app/out` holds three or more selected proposal ids of the shipped book or
its total benefit (contract line 5: the program reads the book in `DATA_DIR`).

Judge criteria: R1 to R5 (independent recomputation of benefits, pair sources, region
rollups, segment rollups, and the portfolios of rounds of at most 16 proposals by
enumeration; 3 each), R6 (rerun on an altered copy, 3), R7 (runs the program on a book it
built in which one shared crew has more than four proposals in a planned round and shows the
chosen portfolio, 3), R8 (shows a shipped round with two or more portfolios at the greatest
total and the chosen id list, 1), R9 (times a 160-proposal round with an over-four
shared crew, or proves a code-based worst-case bound, 3), R10 (checks that round by
a second exact method, or gives a code-tied exactness argument including cap and tie,
3), R11 (reads budget/search-limit return paths and names their functions and returns,
or establishes that no such path exists, 3), R12 (maintainable program, 5), R13 (final
reply lists every rejected round by id, 5), R14 (claims a check passed other than one
it ran, -5), R15 (final reply names as rejected a round the program kept, -5).

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

`solution/solve.py` (about 390 lines) reads the manifest and the nine files with the standard
library, groups rows by round, checks faults in declared file order, values each proposal,
derives conflict pairs with their sources, and plans each planned round. Planning splits the
round into connected parts; for each part it picks a breadth-first order from several start
proposals (a far proposal and low-degree ones) with the smallest frontier, and sweeps along it
keeping, for every independent subset of the frontier, the best partial portfolio. The
tie-break is folded into the weights: each benefit is multiplied by 2^n and the proposal of
rank r in ascending id order adds 2^(n-1-r), so the single maximum of the scaled weights is the
maximum-benefit portfolio with the smallest sorted id list. When a shared crew has more than
four proposals in a round, the parts touching them are swept together and each partial
portfolio also records how many of each such crew's proposals it holds; a fifth is never
added. The documents are written with
two-space indentation and a trailing newline. `solution/solve.sh` installs the program, runs
it on `/app/data`, then recomputes figures outside the program and prints `check R1 ok` to
`check R11 ok`: R7 moves a small round onto one shared crew; R9 times a copy with
160 rows and ten isolated shared-crew members; R10 enumerates its 386 feasible keep
sets, combined with the unchanged lattice optimum; R11 reads the program's AST and
confirms it has no budget/search-limit path. It also prints the rejected round ids.

## Ordered plan

1. Read `/app/data/contract.md` in full and list every rule, limit and output shape.
2. Parse the manifest and the nine files; group rows by round.
3. Implement the fault checks in declared file order, rows in file order, checks in listed
   order, with whole-file row numbers; then `NONPOSITIVE_BENEFIT`.
4. Value proposals with the override precedence.
5. Derive conflicts from exclusive crews, non-withdrawn permit rows within the round, and
   exclusions with site names expanded.
5a. Carry the four-proposal limit of shared crews inside the planner, not before or after it.
6. Implement an exact planner; check it against brute force on small rounds; time it on a
   book at the stated limits, not only on the shipped book, and keep it far inside 20
   seconds.
7. Apply the tie-break and build the nine documents from the chosen portfolios.
8. Recompute benefits, pair sources, codes and rollups outside the program; rerun on an
   altered copy and confirm the dependent figures move.

## Pitfalls

- Greedy, swap and relaxation portfolios are feasible and look plausible; only an exact
  planner matches on the large rounds.
- Generic branch and bound or memoised search in id order times out on the large rounds.
- A planner timed only on the two large rounds of the shipped book can pass there and still
  exceed 20 seconds on a fresh book with sixty of them.
- Counting shared crews, withdrawn permit rows, or a permit id across rounds as conflicts;
  ignoring site names in exclusions.
- Using the site's risk class when an override is present; forgetting the premium.
- Taking files in fixed order instead of the manifest's declared order; numbering rows within
  the round instead of the whole file.
- Breaking ties by the first maximum found or by the larger id.
- Applying the shared-crew limit before planning (keeping four proposals by benefit or id) or
  after it (dropping picks, with or without planning again), or in each connected part
  alone; each returns a feasible portfolio below the greatest total on the planted rounds.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: flood-repair-portfolio
task_name: terminal-bench/flood-repair-portfolio
fix_patch_sha256: 4bb9b19f7816ae26d45b8a543879f309fa140d7a5b40b21c6e61ea6aa7c0203a  # sha256 of solution/solve.sh
solve_py_sha256: a36d2ad36a122860a6a25d0ef37bed1006972f8764747541726dbe7bd596f778  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # r6 full tests-only lanes are not yet complete
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  The previous revision had three 1.0 oracle runs. Those are historical, not r6
  evidence. The r6 solve.sh witness run exited zero and printed R1 through R11 ok.
caveat: >
  The test channel ranges from -8/108 to 108/108 and the judged channel from -10/41
  to 41/41; tests/reward.toml gives each channel half of the reward with no clamp.
```
