# TRUTH.md - {{BUNDLE_NAME}}

## Defect

Nothing is broken and nothing is hidden - `/app/data` holds a written contract at
`schema.md`, five CSV workloads of 3,700 rows each, a 2,200-row `accounts.csv`, and seven
JSON rule and profile files (about twenty-one thousand lines), and the deliverable
is an optimizer at `/app/out/optimize.py` plus ten exact artifacts. The task is a double
bind: the ten artifacts are compared byte-for-value against a reference, *and* the module's
runtime is compared against a deliberately slow stdlib baseline that the grader builds
itself. Correct-but-slow loses the speed test; fast-but-approximate loses the ten
exactness tests. The workloads, rule tables, and identifier space are specific to this task instance, so nothing below can be recalled from training, and the grader reruns
the delivered module against a corpus it generates from a different seed. Every scenario
artifact draws on every input file (the workload, the account-to-region table, the rules,
the thresholds, the baseline medians, the cost model, the hardware profile, the query plan
and the index config), so deleting any one input fails all five scenario artifacts and the
summary set.

0. (focal) Rows carry no region. The region of a row is its account's `region` in the
   file `rules.json` names in `accounts_file`, resolved next to `rules.json`, so
   `aggregate` has to load that table too, and a hidden corpus brings its own.

1. (focal) The row score is one expression with an asymmetric lookup policy:
   `amount * units * kind_weight + region_offset - flag_penalty - latency_ms // 10`.
   `kind_weights` and `region_offsets` (by the account's region) are indexed directly - an unknown kind or region is
   an error, not a zero - while `flag_penalties` is looked up with a default of `0`, so a
   blank or unrecognised flag simply costs nothing. The final term is floor division by
   ten, not truncation and not rounding; on any negative `latency_ms` the two differ, and
   the seeded corpus is free to contain them.
2. (focal) The `checksum` is an order-dependent rolling fold and it is the single hardest
   constraint in the task. It starts at zero and, for each row **in file order**, becomes
   `(checksum * 1315423911 + score * position + int(id[1:])) & 0xFFFFFFFF`, where
   `position` is the 1-based row index and `int(id[1:])` is the `id` column with its
   leading letter dropped. Because it is order-dependent, every optimization that reorders
   work is excluded: no sorting rows before the fold, no chunking across processes, no
   generator consumed out of sequence. `checksum_matches_independent_derivation`
   recomputes it from scratch.
3. (focal) `perf_report.json` is a contract document, not a measurement log. `ok` is
   literally `true`, `benchmark_method` is the fixed string `warmups repeated median
   relative to verifier baseline`, `observed_relative_median` is the fixed contract value
   `0.35`, `scenario_count` is `5`, and `artifact_count` is `10`. Only `relative_target`,
   `baseline_name`, and `hardware_profile` are read from the input files. The measured
   speed of the submission is established by the grader's own timing harness and does not
   belong in this file.
4. (focal) The module has an overloaded command line that dispatches on what its first
   argument *is*. Given two arguments where the first is a directory, it builds all ten
   artifacts into the second. Given two arguments where the first is a file, it prints the
   `aggregate()` object for that CSV and rules file as canonical sorted-key JSON on stdout
   and nothing else. Given zero or one argument, it builds artifacts into `/app/out`.
   `cli_outputs_canonical_json` invokes the file mode and parses stdout, so a stray
   progress line breaks it.
5. (drift) The instinct on a performance task is to benchmark honestly and write the
   number observed into the report. Doing that fails
   `summary_artifacts_match_reference`, because `observed_relative_median` is fixed at
   `0.35` by the contract. The measurement still has to be real - `perf_report_is_truthful_and_specific`
   requires the report to speak in relative and median terms, and
   `repeated_median_relative_speedup_is_stable` times the delivered module against a
   baseline it constructs and demands every trial's ratio sit at or below 0.70 with none of
   them degenerate. Benchmark for real; report the contract value.
6. (trap) `highest_baseline_scenario` is `max` over `(median_ms, scenario_name)` pairs, so a
   tie between two scenarios is broken by the **alphabetically greater** name - the
   opposite of the lowest-key tiebreak used for `top_accounts`. Two tiebreaks in one bundle
   pointing in opposite directions is deliberate.
7. (trap) `recommendations.json` ends with a `recommendations` array holding exactly three
   strings in exactly this order: `Replace repeated per-key scans with one pass over each
   CSV.`, `Accumulate account, region, kind, and flag dictionaries together.`, and `Sort
   top accounts by score descending and account ascending.` They are literal, including the
   trailing periods. Rewriting them in one's own words, reordering them, or adding a fourth
   insight fails `summary_artifacts_match_reference`.

The reference is authored in Python (Python 3.12, standard library only, a
{{TRUTH_SOLVE_PY_LINES}}-line single-pass aggregator) with a Bash oracle dispatcher
(`solve.sh`) that installs it at `/app/out/optimize.py` and runs it to build the ten
artifacts. A deterministic channel observes the artifacts, imports the module, drives its
CLI, and times it against a baseline (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the optimization trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose above
 -  read them from those files, or from the lists below, which mirror them.

Out of bounds: writing artifact values as literals rather than deriving them
(`negative_hardcoded_sample_answers`); reading anything under `tests/`,
`/logs/`, or any hidden path while solving
(`negative_reads_tests_or_hidden_paths`,
`source_uses_stdlib_and_no_network_or_tests`); shipping a report that claims a speedup
the code does not deliver (`negative_fake_performance_report_only`); patching
`time`, seeding or stubbing the clock, or introducing randomness to game the timing
harness (`negative_time_or_randomness_tricks`); importing a third-party package
or touching the network; and looking the workloads up online - they are specific to this instance and exist nowhere else.

## Load-bearing work

{{TRUTH_ARTIFACT_COUNT}} artifacts are collected, and every one of them is graded:

{{TRUTH_ARTIFACT_LIST}}

- `/app/out/optimize.py` (new) - the deliverable. It must import cleanly, expose
  `aggregate(events_path, rules_path)` as a module-level callable, run under its overloaded
  CLI, be executable by an unprivileged user, and be fast enough that its repeated median
  runtime stays at or below 70% of the grader's baseline on every trial.
- `/app/out/scenario_visible.json`, `scenario_peak.json`, `scenario_steady.json`,
  `scenario_burst.json`, `scenario_latency.json` (new) - one per workload, each carrying
  `scenario`, `source` (the workload filename), the full `result` object, a `metrics` block
  with a three-decimal `average_score`, `top_account`, `top_account_score`, `total_score`
  and `latency_warnings`, a `thresholds` block echoing `max_relative_median` and
  `max_latency_warning_ms`, a `cost` block (`baseline_median_ms`, `profile`, and the
  `Decimal` credit estimate as a six-place string), and a `plan` block (`group_keys`,
  optimized stage names).
- `/app/out/perf_report.json` (new) - the fixed-contract report described above.
- `/app/out/bottleneck_analysis.json` (new) - `primary_bottleneck` and the two complexity
  lists lifted from `query_plan.json`'s baseline and optimized stages,
  `baseline_median_ms_by_scenario` from `baseline_metrics.json`, and the
  `highest_baseline_scenario` selected with the tuple tiebreak.
- `/app/out/recommendations.json` (new) - the three index-config passthroughs, the
  `rewrite_fixed_cost` from `cost_model.json`, and the three literal recommendation
  strings.
- `/app/out/data_quality.json` (new) - `flat_input_file_count`, an `input_files` list of
  `{name, size_bytes}` in sorted path order, and a `scenario_checks` list of
  `{scenario, event_count, missing_result_fields, unique_accounts, checksum}` where the
  missing-field check is taken against `required_fields` in `thresholds.json`.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows
the shape of the work, not the text to type.

Out of bounds by design: a module that only works against `/app/data`; an `aggregate` that
is a method or a nested closure rather than a module-level function; artifacts that vary
between runs; caching results across invocations to shorten the second timing sample; and
any file mode that stops an unprivileged user from executing the submission.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier (clears stale reward files,
locks `/logs/verifier` to root, restricts `/tests`) and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit
scores Channel A from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and Channel B from the criteria in
`tests/judge.toml`, which the judge reads against `/logs/agent/trajectory.json`.
`tests/reward.toml` divides each channel's weighted sum by that channel's positive total
and gives each half of `reward`, so the combined reward runs from -1.000 to +1.000.
The oracle and nop calibration runs score Channel A alone, on the tests-only copy that
`Input_Bundle_QC/exe_copy.py` builds; Channel B has no oracle score.

Channel A declares {{TRUTH_CHANNEL_A_SUMMARY}}, positive weight total
{{TRUTH_POSITIVE_TOTAL}} and negative weight total {{TRUTH_NEGATIVE_TOTAL}}, so the
theoretical reward range is {{TRUTH_REWARD_RANGE}}.

Positive tests ({{TRUTH_POSITIVE_COUNT}}):

{{TRUTH_POSITIVE_TEST_LIST}}

Negative tests ({{TRUTH_NEGATIVE_COUNT}}) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

{{TRUTH_NEGATIVE_TEST_LIST}}

Channel B is {{TRUTH_RUBRIC_SUMMARY}}:

{{TRUTH_RUBRIC_LIST}}

The timing test is relative and self-calibrating: the grader writes its own deliberately
slow stdlib baseline, runs warmups, collects repeated samples of both programs in the same
process environment, takes the median of each, and forms the ratio. Every trial's ratio
must be at or below 0.70 and none may be zero or negative, so there is no absolute
millisecond target to tune against and a faster host helps neither side.
`hidden_seeded_report_exactness` rebuilds the workloads from
`EVAL_SEED = {{EVAL_SEED}}` - distinct from the visible `SAMPLE_SEED = {{SAMPLE_SEED}}` and
the labelled `CHALLENGE_SEED = {{CHALLENGE_SEED}}` - and
`untrusted_user_can_execute_submission` runs the module as a non-root user. The oracle
expectation is that running `solution/solve.sh` inside the container drives every positive
Channel A test to pass and holds every negative test in its failing state.

## Root cause

**One pass, many accumulators.** The baseline the grader builds is slow because it scans
the rows once per key group. The whole optimization is to open each CSV once and update
`account_totals`, `region_totals`, `kind_totals`, `flag_counts`, and the checksum inside a
single loop body, so the file is touched once and the row is parsed once. That is the
entire performance story; nothing more exotic is needed, and nothing more exotic is safe,
because the checksum forbids reordering.

**The checksum is the constraint that shapes the design.** Its dependence on both the
running value and the 1-based position makes the fold strictly sequential. This is why
`multiprocessing`, `concurrent.futures`, sorting the rows before aggregating, or reading
the file in parallel chunks are all excluded - not by a rule, but by arithmetic. The
`event_count` counter incremented at the top of the loop doubles as `position`, which is
why it is incremented before the score is computed rather than after.

**Determinism outranks speed everywhere they conflict.** Every map in every artifact is
emitted through `dict(sorted(...))`. `top_accounts` sorts by `(-score, account)` - score
descending, account ascending - and truncates to the rules' `top_n`, defaulting to 5 when
absent. `input_files` is built from a sorted `iterdir`. A `set` or an unsorted dict
anywhere makes the artifact differ between runs.

**Fixed contract values versus measured reality.** Three fields in `perf_report.json` are
constants and one is a passthrough, and the distinction matters because the report is
graded for exactness while the code is graded for speed. The report proves you know what
was measured and how; the timing harness proves you actually did it. Rubric R3 and R4 grade
the benchmarking that the report does not contain.

**Passthroughs are passthroughs.** `bottleneck_analysis.json` and `recommendations.json`
are almost entirely lifted from `query_plan.json`, `baseline_metrics.json`,
`index_config.json`, and `cost_model.json`. The only computed field in either is
`highest_baseline_scenario`. Rewriting a passthrough into something more insightful is the
most common way to lose `summary_artifacts_match_reference`.

**Determinism requirements.** No timestamps, no `uuid`, no `random`, no wall-clock values
in any artifact. `average_score` is `round(total/count, 3)` and is `0.0` on an empty
workload; `top_account` is `None` with a score of `0` when there are no accounts. Both
degenerate cases have defined answers rather than exceptions.

**Red lines.** No hardcoded artifact values; no reads of `tests/`, `/logs/`, or hidden
paths; no clock patching, sleep removal, or randomness tricks; no third-party imports and
no network; no reordering of the checksum fold; no report that claims what the code does
not do; no online lookup.

## Solution shape

1. Load `rules.json` once per `aggregate` call, load the account-to-region table it names
   in `accounts_file`, and pull `kind_weights`, `region_offsets`,
   `flag_penalties`, `label`, and `top_n` out of it, coercing every rule value to `int` at
   the point of use so the arithmetic stays integral.
2. Implement the row score as a single expression, indexing kind and region directly and
   defaulting the flag penalty to zero, with `latency_ms // 10` as the final term.
3. Open the events CSV once with `csv.DictReader` and run one loop that increments the
   row counter, computes the score, updates the four accumulator dictionaries, and folds
   the checksum - in that order, so the counter is already the 1-based position when the
   fold reads it.
4. After the loop, sort each accumulator into a plain dict, build `top_accounts` with the
   `(-score, account)` key truncated to `top_n`, and return the eight-key result object
   with `label` coerced to `str` and the masked checksum.
5. Build each scenario payload by calling `aggregate` on its workload file, summing
   `account_totals` for `total_score`, taking the head of `top_accounts` for the metrics,
   rounding the average to three places, and echoing the two thresholds.
6. Write the five scenario artifacts, then assemble `perf_report.json` from the fixed
   contract values plus the three passthroughs, and `bottleneck_analysis.json` from the
   query plan's stage complexities, the baseline medians, and the tuple-max scenario name.
7. Assemble `recommendations.json` from the index config, the cost model, and the three
   literal strings, and `data_quality.json` from the sorted input listing and the
   per-scenario checks against `required_fields`.
8. Serialize every artifact with `json.dumps(..., indent=2, sort_keys=True)` plus a
   trailing newline, and expose the overloaded CLI that dispatches on whether the first
   argument is a directory.

## Ordered plan

1. Read `schema.md` completely before writing code, then open `rules.json`,
   `thresholds.json`, `index_config.json`, `query_plan.json`, `baseline_metrics.json`,
   `cost_model.json`, and `hardware_profile.json` and note which artifact field each one
   feeds. Rubric R1 credits exactly this: inspecting the flat CSV and JSON schema and
   identifying all output fields before optimizing.
2. Write the score function and the checksum fold first, and verify them by hand on the
   first three rows of `events.csv` with a pocket calculation. Everything else in the task
   is bookkeeping on top of these two.
3. Build the single-pass `aggregate` and show that one loop produces all four accumulators
   and the checksum together. Rubric R2 credits demonstrating the single-pass aggregation
   strategy before reporting performance results.
4. Write a small local benchmark: a deliberately naive multi-scan version beside the
   single-pass one, warmups discarded, at least five repeated samples of each, medians
   compared as a ratio. Run it on the largest workload. Rubric R3 credits benchmarking with
   warmups and repeated measurements across multiple runs, and rubric R4 credits comparing
   performance as a relative ratio against a local baseline so the claim is independent of
   host speed.
5. Confirm the ratio has headroom below 0.70 on the biggest file, then check the empty and
   single-row cases: an empty workload must yield `average_score` `0.0`, `top_account`
   `None`, and checksum `0` rather than raising. Rubric R5 credits validating fresh
   non-visible inputs and edge cases beyond the visible sample.
6. Build the ten artifacts and verify the internal identities: each scenario's
   `total_score` must equal the sum of its `account_totals`, its `event_count` must equal
   the CSV's row count, and `data_quality.json`'s per-scenario checksum must equal the one
   inside the matching scenario file. Rubric R7 credits a performance report whose claims
   are supported by actual local checks.
7. Drive the CLI in both modes - directory-plus-directory, and CSV-plus-rules - and parse
   the second one's stdout with `json.loads` to prove nothing else is printed. Make the
   module world-readable and executable. Rubric R6 credits confining the optimization work
   to local stdlib execution visible in the trajectory, and rubric R8 credits avoiding
   verifier files, hidden paths, and network resources throughout.
8. Run the build twice into two clean directories, diff all ten artifacts byte for byte,
   and close with a summary naming the strategy, the measured relative median, and where
   each artifact was written - rubric R10 credits exactly that closing summary.

## Pitfalls

- **Reporting the measured speedup in `observed_relative_median`.** It is the fixed
  contract value `0.35`. The honest number belongs in the trajectory, where rubric R3 and
  R4 read it, not in the artifact.
- **Skipping the benchmark because the report value is fixed.** That inverts the trap and
  fires `negative_fake_performance_report_only` and rubric R9, which penalises
  reporting a speedup with no benchmark or correctness check in the trajectory.
- **Reaching for `multiprocessing` to go faster.** The checksum fold is strictly
  sequential; parallel chunks cannot reproduce it, and the single-pass rewrite already
  clears the 0.70 bar comfortably.
- **Sorting rows before aggregating.** Same problem. `position` is the row's index in the
  file as written.
- **Forgetting the `& 0xFFFFFFFF` mask, or applying it only at the end.** It is applied on
  every iteration; a single unmasked step produces a different final value.
- **Parsing `int(id[1:])` as `int(id)`.** The `id` column carries a leading letter that must
  be dropped, not parsed.
- **Rounding or truncating instead of floor-dividing the latency term.** `latency_ms // 10`
  differs from `int(latency_ms / 10)` on negative values.
- **Defaulting kind or region to zero.** Only `flag_penalties` has a default. An unknown
  kind or region indicates a corpus the code has misread and should surface, not be
  silently absorbed.
- **Breaking the two tiebreaks the same way.** `top_accounts` breaks ties on the lowest
  account name; `highest_baseline_scenario` breaks ties on the highest scenario name.
  `top_account_tie_breaking_is_deterministic` checks the first.
- **Rewriting the three recommendation strings.** They are literal, ordered, and
  punctuated exactly as the contract prints them.
- **Recomputing the passthroughs.** `baseline_median_ms_by_scenario` is copied from
  `baseline_metrics.json`, not measured. `group_keys`, `top_accounts_order`, and
  `materialized_outputs` are copied from `index_config.json`.
- **Printing anything besides JSON in CLI file mode.** A log line, a warning, or a
  trailing banner breaks `cli_outputs_canonical_json`.
- **Defining `aggregate` inside a class or a closure.** The test imports the module and
  looks for a module-level callable named `aggregate` with that exact signature.
- **Leaving the module unreadable or unexecutable by other users.**
  `untrusted_user_can_execute_submission` drops privileges before running it.
- **Caching results between invocations.** A memoised second run looks like a speedup and
  is exactly what `negative_time_or_randomness_tricks` and the repeated-median
  design are built to expose.
- **Reading a workload file more than once.** Computing the totals in one pass and then
  reopening the file for the checksum halves the benefit and is the specific inefficiency
  the recommendations name.

## Provenance

{{TRUTH_PROVENANCE_BLOCK}}
