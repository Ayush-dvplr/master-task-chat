# TRUTH.md - cohort-retention-reconciliation

## Defect

There is no broken program to repair. `/app/data` holds the study extract, the
contract `/app/data/schema.md`, the audit policy `/app/data/audit_policy.md` and
the export job's `extract_manifest.json`, and the deliverable is a reusable
derivation program that turns any extract of this shape into the exact JSON
report artifacts. The difficulty is a serial chain where each stage consumes the
exact output of the one before it: raw rows are tested for shape, calendar,
repeats, merge identity, exclusion and account membership; the cleaned set
decides each account's cohort; cohort membership decides the activity matrix,
the retention rates and the survival curve; and the revenue ledger, booked in
cleaned order against a per-account balance and weighted by the plan or segment
weight in force, feeds the revenue maps, the weighted shares, the segment
rollups, the per-cohort documents and the reconciliation residuals. The grader
reruns the delivered program on three regenerated hidden studies and compares
whole documents, so a correct answer has to implement the contract in general
rather than match the shipped figures.

1. (focal) Identifiers match across files once surrounding spaces are removed and
   letters are lower-cased: account ids in every file, event types in
   `events.csv` and in the lists of `qualifying_rules.json`, plan names and
   segment codes (`schema.md`, Identifiers). The hidden studies spell ids in
   `accounts.csv`, `account_merges.csv`, `exclusions.csv` and `plan_history.csv`,
   segment codes, plan names and the rule lists in other case or with spaces,
   and write case variants of events, including repeats of an earlier row. A
   program that normalises only `events.csv`, or compares the duplicate key as
   raw text, loses accounts, keeps excluded ones and miscounts duplicates.
   `identifiers_match_across_files`, `mutation_minimum_moves_cohort_sizes` and every `hidden_*` document grade it.
2. (focal) Every other field is read exactly as written, so a `value_cents` or
   `event_date` with a surrounding space is malformed (cleaning step 1). The
   shipped extract carries `e035` (` 4500`). A loader that trims every field
   keeps those rows and, in the hidden studies, moves a cohort through a spaced
   early qualifying date. `spaced_values_and_dates_are_malformed` and the hidden
   documents grade it.
3. (trap) `extract_manifest.json` records `data_rows` per file and, for
   `events.csv`, a `value_cents_sum` its note defines over values read with
   surrounding spaces removed. On the shipped extract the manifest matches only
   under that definition: a sum taken over strictly parsed values is 4500 short
   (`e035`), which invites a repair that trims values in the cleaner and breaks
   item 2. `control_mismatches` lists every disagreeing figure and
   `control_value_residual_cents` carries the value gap. Each hidden study ships
   three faulty manifest figures in three files, written in an order that is not
   sorted; the `events.csv` `value_cents_sum` figure equals the strictly parsed
   sum, so it disagrees only under the note's definition and the residual is
   minus the space-padded values. `manifest_figures_follow_its_note`,
   `hidden_data_quality` and `hidden_reconciliation` grade it.
4. (focal) Revenue is booked one event at a time in cleaned order (date, resolved
   account, event type). A purchase books its value and adds it to the resolved
   account's refundable balance; any other revenue type books minus the smaller
   of its value and the balance, and the rest is unhonored. `chargeback` and
   `credit_note` sort before `purchase` on the same day, so they meet the balance
   before that day's purchase. The balance belongs to the resolved account, so a
   refund written against a merged-away id draws on the successor's balance.
   `balance_belongs_to_the_resolved_account`, `hidden_revenue`,
   `hidden_segments` and `hidden_per_cohort_documents` grade it.
5. (focal) The weight of an event is the `plan_weights.json` weight of the plan
   in force on its date for the resolved account (`audit_policy.md`, Plans),
   unless the `segments.csv` row for that resolved account's segment has a
   non-empty `weight_override`, which replaces it. `schema.md` speaks only of
   "the weight of the plan in force"; the override sits in the audit policy.
   `study_audit.json` echoes the filled overrides. The shipped overrides are
   blank. `segment_override_follows_the_resolved_account`,
   `mutation_override_moves_only_weighted_revenue`, `hidden_revenue`,
   `hidden_segments` and `hidden_study_audit` grade it.
6. (drift) The cleaning stages run in a fixed order and a removed row is counted
   once; the register lists every reason whose test the raw row meets; merges
   apply on or after `effective_from`, chain, and the latest applicable row wins;
   cohorts come from the earliest qualifying event at or above
   `minimum_value_cents`; pre-cohort activity is counted apart; survival is a
   running minimum; rates are exact reduced fractions. The hidden documents grade
   these. Each regenerated study also carries a same-day purchase pair from two
   pre-merge ids that resolve to one account (both kept) and a repeated
   in-calendar row for the excluded account (the repeat is counted under
   duplicate), so `hidden_revenue`, `hidden_segments`, `hidden_data_quality` and
   `hidden_per_cohort_documents` grade the duplicate key and the stage order.
   Side rows, drawn from a second seeded stream so the rest of a study is
   unchanged, trigger the remaining stated rules: an account with an undrained
   same-day purchase and refund (the refund sorts first and is unhonored), an
   account whose only cohort is the last period and has no revenue events (0 in
   every revenue map), a second merge row for the ghost id with the same
   `effective_from` placed before the winning row (the later row wins), period
   numbers that cross from 9 to 10 so name order differs from calendar order,
   and `offset_zero_is_full` false in the first hidden study.

## Load-bearing work

The collected paths are `/app/out/derive_report.py`, which must run as
`python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, and the report files
`cohorts.json`, `retention.json`, `survival.json`, `revenue.json`,
`segments.json`, `data_quality.json`, `reconciliation.json`, `study_audit.json`,
`cohort_2026-P1.json` and `cohort_2026-P2.json` under `/app/out`. The program
must read only the directory it is given, use the standard library only and write
JSON with sorted keys, integers for counts and cents, and a trailing newline.
`plan_prices.csv` feeds no figure. The tests channel grades the program's output
on hidden studies; the shipped report files are checked only for presence and
parse.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. `tests/reward.toml` weights the tests channel and the
judge channel at one half each.

Tests channel (`tests/test_output.py`), nineteen positive checks worth 71:
- Hidden whole documents on three regenerated studies, credit the share of
  studies matched (43): `hidden_cohorts` 5, `hidden_retention` 5,
  `hidden_survival` 5, `hidden_revenue` 5, `hidden_segments` 5,
  `hidden_data_quality` 5, `hidden_reconciliation` 3, `hidden_study_audit` 5,
  `hidden_per_cohort_documents` 5.
- Format and determinism on hidden studies (6):
  `hidden_serialization_is_canonical` 3, `deterministic_rerun` 3.
- Fixtures built from the shipped files, each reading one figure (21):
  `spaced_values_and_dates_are_malformed` 3,
  `identifiers_match_across_files` 3, `manifest_figures_follow_its_note` 3,
  `balance_belongs_to_the_resolved_account` 3,
  `segment_override_follows_the_resolved_account` 3, and two mutation tests,
  `mutation_override_moves_only_weighted_revenue` 3 and
  `mutation_minimum_moves_cohort_sizes` 3.
- Shipped files (1): `artifact_set_exists_and_parses` 1.

Five negative checks worth -23: `negative_hardcoded_sample_answers` -5,
`negative_reads_tests_or_reward_files` -5, `negative_external_dependency_or_network`
-3, `negative_filename_dependent_behaviour` -5,
`negative_reads_training_corpus_at_runtime` -5.

Deviation from the bool rule (TS-29): the nine hidden-document checks return a
float, the share of the three hidden studies matched (0, 1/3, 2/3 or 1), so one
wrong study costs a third of the check rather than all of it; rewardkit 0.2.1
accepts any score in [0, 1]. Every other check returns 1.0 or 0.0. No check
raises: `_passes` turns any exception into 0.0.

The grader runs the program as `nobody` through `setpriv`, after granting read on
the program and its directory, serialised by a file lock, and kills leftover
processes by process group and by uid. A check that loses credit prints a
`check note:` line with the assertion text to the verifier log.

Judge channel (`tests/judge.toml`), eight criteria: R1 to R5 (3 each) ask
whether the agent ran its program on an extract it built that exercises a case
the shipped data lacks (a disagreeing manifest figure, an id spelled differently
outside `events.csv`, a spaced `event_date`, a subtraction beyond the balance, a
filled `weight_override`) and checked the matching output; R6 (3) asks that
every except clause in the program names an exception type and raises again or
reports the error; R7 (1) asks that the program ran on `/app/data` after its last
edit; R8 (-5) is a negative for claiming a check passed while its own output
shows otherwise.

Shipped figures from the reference: total revenue 35700 cents, weighted revenue
total 138900, unhonored 0, clean events 23 of 35, malformed 3, register 12 rows
with 15 reason entries, `control_mismatches` empty.

## Root cause

**Two definitions of one figure.** The manifest's value sum trims, the cleaner
does not; matching the control by trimming in the cleaner is the wrong repair.

**One identifier rule for every file.** The shipped extract writes every id in
one spelling, so a program that normalises only where it sees a variant passes
the shipped data and fails the hidden studies.

**State carried down the ledger.** A subtraction's booked amount depends on the
earlier events of the resolved account in cleaned order, so file order, raw ids
or an uncapped sum all give different revenue.

**Exception in another file.** The weight rule in `schema.md` names the plan; the
override for a segment is in the audit policy and depends on the resolved
account's segment.

## Solution shape

1. `load_rows` and `load_json` load every input; `ident` normalises identifiers;
   `fraction_text` renders reduced fractions.
2. `strict_day` applies the `ISO_DAY` regular expression to the field as written
   and then parses the date; `WHOLE_CENTS` tests the value as written.
3. `Timeline` keeps dated values per normalised key and returns the one in force
   on a day: the latest start on or before it, the later file row on a tie. It
   serves both the merge rules and the plan history.
4. `check_manifest` counts each manifest figure from the delivered file as the
   note defines it (`manifest_value_sum` trims values) and returns the
   mismatches and the value residual.
5. `load_extract` gathers the inputs into an `Extract`, which finds a date's
   period by bisecting the calendar, follows merge chains at a date with a cycle
   guard (`owner_on`) and returns the override or plan weight in force
   (`weight_on`).
6. `tag_rows` gives every raw row its full reason set on the normalised key;
   `audit` filters the tagged rows in policy order, keeps the first of each key
   among the rows still standing, and sorts the clean rows by date, resolved
   account and event type.
7. `build_study` assigns cohorts, counts pre-cohort activity, collects active
   periods and runs the revenue ledger with a balance per resolved account;
   `Study` derives the offset counts and the running-minimum survival.
8. One builder per report (`cohorts_report` to `cohort_report`) shapes each
   document, and `save` writes each with `indent=2`, sorted keys and a trailing
   newline.

## Ordered plan

1. Read `schema.md`, `audit_policy.md` and the manifest note; list every input
   each rule governs.
2. Write the shape tests on fields as written, the identifier normalisation for
   every file, and the staged cleaner with the full reason register.
3. Resolve merges by event date and the weight in force (plan, then segment
   override) for the resolved account.
4. Build cohorts, matrix, survival, the revenue ledger with balances, segments,
   control figures and residuals.
5. Build small extracts that exercise the cases the shipped data lacks and check
   the matching outputs (R1 to R5).
6. Run the program on `/app/data`, read the reports back (R7) and claim only
   checks whose output agrees (R8). The reference validates dates without a
   try block, so it has no except clause that hides an error (R6).

## Pitfalls

- **Trimming every field in the loader.** Keeps ` 4500` and spaced dates; fails
  `spaced_values_and_dates_are_malformed` and most hidden documents.
- **Summing the control over strictly parsed values.** Reports a false
  `events.csv:value_cents_sum`; fails `manifest_figures_follow_its_note`,
  `hidden_data_quality` and `hidden_reconciliation`.
- **Normalising ids only in `events.csv`.** Fails
  `identifiers_match_across_files`, the minimum mutation and every hidden
  document.
- **Raw-text duplicate key.** Fails the hidden documents.
- **Uncapped subtraction, file-order ledger or balance on the raw id.** Fails the
  balance fixtures and the hidden revenue, segment and per-cohort checks.
- **Ignoring `weight_override`, or taking the segment of the raw id.** Fails the
  override fixture, the override mutation and the hidden revenue, segment and
  study-audit checks.
- **Floats, booleans or unsorted keys.** Fail `hidden_serialization_is_canonical`
  and the document checks. That check and `deterministic_rerun` also require the
  exact document set of the study and the reference `cohorts.json`.
- **Naming the verifier's files in the program.** Fires
  `negative_reads_tests_or_reward_files`.

## Provenance

```yaml
uuid: null  # task.toml carries no uuid field
instance_id: cohort-retention-reconciliation
task_name: terminal-bench/cohort-retention-reconciliation
solve_sh_sha256: c054a4847422053093453d586a4da399785559654f49913d1ba81287dcbb966d  # sha256 of solution/solve.sh
solve_py_sha256: bf91bc6f53941b282e4c208d227d5884b7ae0bc8d877a120c9778ea658cbdf13  # sha256 of solution/solve.py, 552 lines
language: python
caveat: >
  The tests channel carries 19 positive checks worth 71 weight and 5
  polarity-inverted negative checks worth -23. The judge channel carries 8
  criteria, seven positive worth 19 points and one negative worth -5. Each channel
  gives half of the reward through tests/reward.toml, so the theoretical reward
  range is about -0.29 to +1.00.
```
