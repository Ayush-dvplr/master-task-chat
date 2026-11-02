# TRUTH.md - fdc5a20d-2dfe-5f64-a3fa-2c023318a760

## Defect

Nothing under `/app` computes anything when the agent starts. `environment/Dockerfile`
copies `data` into `/app/data` and stops there, so the container holds six read-only
inputs - `records.csv`, `model.json`, `feature_spec.json`, `scoring_policy.json`,
`SCHEMA.md`, `metrics_reference.md` - and no scorer. The agent must build a batch
scoring pipeline that turns those inputs into an exact aggregate report at
`/app/report.json`, and must package the same derivation as a reusable
standard-library-only script at `/app/derive_report.py` that accepts its four inputs
and its output path on the command line. The difficulty is not that anything is
withheld: `SCHEMA.md` and `metrics_reference.md` state every rule with a worked
example. The difficulty is that three of those rules chain onto one spine - the
per-record probability - so a slip in any of them moves every downstream aggregate at
once.

1. (focal) No artifact exists. `/app/report.json` and `/app/derive_report.py` are both
   absent, so the schema, the canonical byte format and the whole-report comparisons
   have nothing to grade. This defeats `report_artifact_exists_and_is_json`,
   `report_schema_is_exact`, `report_canonical_serialization`,
   `visible_report_matches_independent_derivation` and
   `hidden_full_report_matches_fresh_derivation`.
2. (focal) The numeric path is three stages, not one. A raw cell is imputed with the
   declared `impute` value when blank, standardized as `(value - mean) / std` with a
   zero `std` collapsing to zero, then held to `clip_lo`/`clip_hi`, and only then
   expanded into one hinge key per declared knot - `f|1` for the first knot, `f|2` for
   the second, each carrying `max(x - knot, 0)` computed from the *clipped* value.
   Implementing the linear term alone, or hinging the unclipped value, defeats
   `fresh_hinge_basis_and_winsorization` and
   `fresh_missing_numeric_imputed_to_declared_value`.
3. (focal) No record scores in isolation. The state starts at zero, the linear score is
   `base + lambda * s`, and the state then advances to
   `round_half_even(alpha * s + (1 - alpha) * score, state_decimals)` before the next
   record. Records are visited in file order, which the hidden corpora deliberately
   emit in descending id order so that file order is never sorted order. Scoring
   records independently, replaying in sorted order, or carrying the unrounded state
   forward each defeat `fresh_carry_state_replays_in_file_order`.
4. (focal) The logistic transform consumes the calibrated score, not the linear one.
   The calibrated score is `score / (temperature_milli / 1000) + prior_shift_micro / 1000000`,
   and the sigmoid must be evaluated branch-wise so that a score of -1000 does not
   overflow `math.exp`. Multiplying by the temperature, or adding the shift before
   dividing, defeats `fresh_calibration_temperature_and_prior_shift`; a naive
   `1 / (1 + exp(-z))` defeats `fresh_sigmoid_extreme_scores_stable`.
5. (drift) The statistically literate instinct is to average the raw probabilities and
   round the mean once, and to round the aggregate at the same precision as the other
   aggregates. The spec says the opposite on both counts: `mean_probability` is the
   arithmetic mean of the already-rounded per-record probabilities, and it rounds at
   `prob_decimals` from `model.json` rather than at `metric_decimals` from
   `scoring_policy.json`. Following the instinct defeats
   `fresh_mean_probability_averages_rounded_values` and
   `fresh_mean_probability_uses_prob_decimals`.
6. (trap) Every selection downstream of the probability compares the *rounded* value,
   the threshold comparison is `>=` so a tie predicts positive, and the borderline band
   is a strict `<` so a record exactly one margin from the threshold is excluded. None
   of this is visible on the twelve-record shipped batch, where no record lands on a
   boundary. It surfaces in `fresh_threshold_tie_counts_as_positive`,
   `fresh_threshold_uses_rounded_probability`,
   `fresh_borderline_uses_rounded_probability`,
   `fresh_top_record_uses_rounded_probability`,
   `fresh_borderline_exact_boundary_is_excluded`,
   `fresh_borderline_band_selection` and `fresh_borderline_ids_are_sorted`.
7. (trap) Degenerate corpora never appear in the shipped inputs. A batch with only a
   header row makes `record_count` zero and therefore the accuracy denominator zero; a
   feature with `std` of zero standardizes to zero rather than dividing; a categorical
   value outside the declared list contributes all-zero indicators instead of raising,
   and a weight key that names no expanded feature contributes nothing;
   a confusion matrix with no predicted positives makes three ratios divide by zero.
   These are graded by `fresh_empty_batch_report_is_zero_filled`,
   `fresh_zero_denominator_ratios_are_zero`,
   `fresh_zero_variance_feature_zeroed`,
   `fresh_unseen_category_contributes_zero` and
   `fresh_positive_label_from_policy`.

The reference implementation is Python 3.12 using only the interpreter's standard
library - `csv`, `json`, `math`, `sys`, `fractions`, `tempfile` and `pathlib` - and the run is graded
on two channels that `tests/reward.toml` weights equally. The test channel is
`tests/test_output.py`, run by rewardkit from `tests/test.sh`; it grades the two
artifacts and the behaviour of the delivered script on freshly synthesized batches. The
judged channel is `tests/judge.toml`, scored by an LLM judge against the agent's
trajectory and its final answer.

Out of bounds: hand-writing `/app/report.json` for the shipped inputs, or embedding a
memorised report inside `derive_report.py` and keying it on the conventional file
names, is caught by `negative_hardcoded_sample_answers`, which hands the
delivered script the visible batch and a copy whose `r0003` row differs and fires when
both runs return byte-identical output. Reaching for `numpy`, `pandas`, `scipy` or any
other non-standard-library module - including one pulled in at run time through
`__import__` or `importlib.import_module` - is caught by
`negative_third_party_dependency`. Letting anything unordered, timed or
seeded leak into the output so that two runs on identical inputs disagree is caught by
`negative_nondeterministic_output`. Branching on the input file names
rather than their content is caught by
`negative_filename_dependent_behaviour`, which runs the same corpus under
`batch.csv`, `coeffs.json`, `columns.json` and `rules.json` and requires the report to
be unchanged. Editing any of the six shipped inputs under `/app/data` is caught on
the judged channel by criterion R11.

## Load-bearing work

Two graded artifacts are declared in `task.toml`:

- `/app/report.json`
- `/app/derive_report.py`

`/app/report.json` carries exactly nine top-level keys: `report_id` echoed verbatim
from `model.json`, `record_count`, `positive_count`, `negative_count`,
`mean_probability`, `class_metrics`, `feature_contributions`, `borderline_record_ids`
and `top_record`. `class_metrics` carries exactly `tp`, `fp`, `fn`, `tn`, `precision`,
`recall`, `f1` and `accuracy`, with the four counts as integers and the four ratios
rounded half-to-even at `metric_decimals`, each defined as `0.0` when its denominator
is zero. `feature_contributions` maps every key in `model.weights` - linear, hinge and
one-hot alike - to the corpus sum of `weight * feature_value`, taken from the base
score inputs so that neither the running state nor the calibration enters it, rounded
half-to-even at `metric_decimals`. `borderline_record_ids` is the sorted list of ids
whose rounded probability sits strictly inside `borderline_margin` of the threshold.
`top_record` is an object of `record_id` and `probability` naming the largest rounded
probability with ties resolved to the lexicographically smallest id, degenerating to a
null `record_id` with `probability` `0.0` on an empty batch. The file is serialized as
`json.dumps(report, indent=2, sort_keys=True)` plus a single trailing newline.

`/app/derive_report.py` must perform the identical derivation from its arguments. It is
invoked as `python3 /app/derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON POLICY_JSON
OUT_JSON`, writes the canonical report to the fifth path, and exits zero within a
25-second budget per invocation. The verifier runs it as an unprivileged user against
corpora it synthesizes at run time, in directories whose file names it chooses, so the
script may not assume `/app/data`, may not cache anything across runs, and may not
depend on argument names. It is the script, not the shipped report, that carries the
majority of the test-channel points.

Out of bounds by design: the six files under `/app/data` are inputs only and must be
left byte-identical; no artifact may be produced by transcribing a precomputed answer;
and no module outside the standard library may be imported by any `*.py` file under
`/app`, since the dependency probe walks the syntax tree of every one of them, not just
the delivered script.

## Verification

`tests/test.sh` clears `reward.txt`, `reward.json` and `reward-details.json`, locks
`/logs/verifier` to `root:root` mode 700, removes group and other access from `/tests`,
and hands over to `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. It writes no reward itself. rewardkit scores two inputs:
`test_output` (the 35 `@criterion` checks in `tests/test_output.py`, each registered
once with `criteria.<name>(weight=W)`) and `judge` (the 11 criteria in
`tests/judge.toml`). `tests/reward.toml` combines them as
`test_output * 0.5/51 + judge * 0.5/17`, so each channel carries half the reward, every
positive passing with no negative firing scores 1.0, doing nothing scores 0.0, and the
floor is -0.5 * 14/51 - 0.5 * 10/17. There is no clamp.

Every check returns a bool and catches its own errors, so bad, missing or hostile
output scores False instead of aborting the run. The delivered script runs as uid/gid
65532 with umask 077 in its own session, with a 25-second budget per invocation, and
its whole process group is killed on every exit path. Each fixture's four inputs live
in a root-owned mode-755 directory with mode-644 files, the script writes into a
separate mode-777 output directory, and every expected report is derived from the
fixture before the script runs, so the script cannot change the truth it is graded
against. Every numeric spec entry carries `clip_lo`, `clip_hi` and `knots`; fixtures
that test another rule use bounds of -1000000 and 1000000 and no knots. Fixtures that
grade a rule downstream of the probability (`fresh_probability_precision_from_model`,
`fresh_probability_half_even_tie_at_prob_decimals`,
`fresh_top_record_tiebreak_smallest_id`, `fresh_borderline_uses_rounded_probability`,
`fresh_mean_probability_uses_prob_decimals`) use an inert state and identity
calibration, so only their named rule decides them. The value comparison is
type-aware: a bool never matches a number, a float never matches an expected int, and
an int is accepted where a float is expected.

Test positives, 31 checks summing to +51:

- `report_artifact_exists_and_is_json` (+1) - `/app/report.json` parses into a JSON
  object.
- `report_schema_is_exact` (+1) - the nine top-level keys, the eight `class_metrics`
  cells and the two `top_record` fields match exactly. It compares key sets only.
- `visible_report_matches_independent_derivation` (+5) - the shipped report equals an
  in-test derivation of the visible twelve-record batch.
- `report_canonical_serialization` (+1) - the report bytes equal
  `json.dumps(..., indent=2, sort_keys=True)` plus a trailing newline.
- `hidden_full_report_matches_fresh_derivation` (+5) - the delivered script reproduces
  the entire report on a 60-record corpus synthesized from `EVAL_SEED`, with blanked
  `f_b` and `f_d` cells, reversed file order, and its own state (alpha 2/5, lambda 3/4,
  `state_decimals` 5) and calibration (`temperature_milli` 1600, `prior_shift_micro`
  -150000), so neither can be copied from the shipped model.
- `fresh_report_canonical_serialization` (+1) - the script's output on an 18-record
  `CHALLENGE_SEED` corpus is canonical JSON.
- `fresh_banker_rounding_precision` (+1) - a precision of exactly 1/8 reports `0.12` at
  `metric_decimals` 2.
- `fresh_zero_variance_feature_zeroed` (+1) - a feature with `std` 0 contributes `0.0`.
- `fresh_unseen_category_contributes_zero` (+1) - `green` and `purple` against declared
  `red` and `blue` leave both indicators at zero, and the weight key `color=purple`,
  which names no expanded feature because `purple` is not declared, sums to `0.0`.
- `fresh_missing_numeric_imputed_to_declared_value` (+1) - a blank cell fills with
  `impute` 30 rather than `mean` 10, standardizes to 4 and is held to `clip_hi` 2, so
  the contribution is `12.0`.
- `fresh_sigmoid_extreme_scores_stable` (+1) - scores of +1000 and -1000 saturate to
  `1.0` and `0.0` without an overflow.
- `fresh_zero_denominator_ratios_are_zero` (+1) - one true-negative record drives
  precision, recall and f1 to `0.0`.
- `fresh_empty_batch_report_is_zero_filled` (+1) - a header-only batch zero-fills every
  count, ratio and contribution and reports a null `top_record.record_id`.
- `fresh_positive_label_from_policy` (+1) - `positive_label` `"yes"` yields one true
  positive.
- `fresh_probability_precision_from_model` (+1) - the logistic of 1.35 reports `0.79` at
  `prob_decimals` 2.
- `fresh_probability_half_even_tie_at_prob_decimals` (+1) - with an inert state and
  identity calibration a zero score gives a raw probability of exactly `0.5`, which
  rounds to `0.0` at `prob_decimals` 0 (half-up would give `1.0`).
- `fresh_threshold_tie_counts_as_positive` (+1) - a probability equal to the threshold
  is positive.
- `fresh_feature_contributions_are_corpus_sums` (+1) - per-weight sums run across all
  records and net to `0.0`.
- `fresh_top_record_tiebreak_smallest_id` (+1) - three exactly tied records in the file
  order `b_rec`, `a_rec`, `c_rec` resolve to `a_rec`.
- `fresh_borderline_band_selection` (+1) - only the record inside the 0.05 band is
  listed.
- `fresh_borderline_exact_boundary_is_excluded` (+1) - a record exactly one margin from
  a 0.375 threshold is dropped by the strict `<`.
- `fresh_borderline_ids_are_sorted` (+1) - ids listed in descending file order come back
  as `["a_rec", "z_rec"]`.
- `fresh_threshold_uses_rounded_probability` (+1) - a raw value just under the threshold
  that rounds onto it counts as positive.
- `fresh_borderline_uses_rounded_probability` (+1) - a raw `0.497500` sits outside a
  0.001 margin but rounds to `0.50` and is listed.
- `fresh_top_record_uses_rounded_probability` (+1) - two raw probabilities that both
  round to `0.8` at `prob_decimals` 1 resolve to `a`.
- `fresh_contribution_half_even_at_metric_decimals` (+1) - a contribution of exactly
  `0.125` reports `0.12` at `metric_decimals` 2.
- `fresh_mean_probability_uses_prob_decimals` (+1) - rounded probabilities `0.12` and
  `0.13` average to `0.125`, reported as `0.12` at `prob_decimals` 2, not `0.125` at
  `metric_decimals` 4.
- `fresh_mean_probability_averages_rounded_values` (+1) - rounded `0.0` and `1.0`
  average to `0.5`, reported as `0.0`; averaging raw values reports `1.0`.
- `fresh_carry_state_replays_in_file_order` (+5) - three identical records must not
  share a probability; a three-record batch and its reverse must each match their own
  derivation (so a sorted replay fails); and a batch declaring alpha 2/5, lambda 3/4 and
  `state_decimals` 1 must match, which pins the state rounding and the reading of the
  declared state settings; and a two-record batch with alpha 1/2, lambda 1 and
  `state_decimals` 1 advances the state to exactly `0.25`, which half-to-even holds at
  `0.2` (half-up gives `0.3`, no rounding keeps `0.25`).
- `fresh_hinge_basis_and_winsorization` (+5) - a raw `7.0` clips to `1.25` and, with
  knots `[-0.75, 0.5]`, yields contributions `x` `2.5`, `x|1` `6.0` and `x|2` `3.75`.
- `fresh_calibration_temperature_and_prior_shift` (+5) - a linear score of `2.24` under
  `temperature_milli` 1600 and `prior_shift_micro` -150000 calibrates to `1.25`, so the
  probability is `0.7773`.

Test negatives, 4 checks summing to -14. Each returns True only when the cheat
happened, and none fires on an empty run.

- `negative_hardcoded_sample_answers` (-5) - first proves the two correct reports
  differ, then fires when the script returns identical bytes for the visible batch and
  its copy with a changed `r0003` row.
- `negative_third_party_dependency` (-3) - walks the syntax tree of every `*.py` in the
  workspace and fires on any import, `from`-import or dynamic import naming a module
  outside `sys.stdlib_module_names` and outside the local files.
- `negative_nondeterministic_output` (-3) - fires when two successful runs on one
  30-record corpus disagree byte for byte.
- `negative_filename_dependent_behaviour` (-3) - runs each of two naming layouts twice
  and fires only when both are individually stable, the script is not content-blind,
  and the reports still differ across the rename, so one mistake costs one penalty.

Judged channel, `tests/judge.toml`, 11 criteria summing to +17 and -10:

- R1 to R4 (+1 each, constraint, judged on the final answer) - the four closing
  statements the instruction asks for: round-half-to-even, all-zero indicators for unknown categories, a threshold tie
  predicting positive, and the state replayed in file order.
- R5, R6 and R7 (+3 each, conduct) - hands-on checks of the three chained rules: two
  records sharing a feature value driven apart by the state, a value beyond its clip
  bound checked against the hinge contributions, and one calibrated score checked
  against a hand-computed logistic value.
- R8 (+1, conduct) - the confusion-matrix cells reconciled against `record_count`.
- R9 (+3, conduct) - `derive_report.py` routes every rounded value through one shared
  half-to-even helper.
- R10 (-5, conduct) - the summary claims a validation the trajectory shows was skipped.
- R11 (-5, constraint, judged on the trajectory) - any edit to the six shipped inputs
  under `/app/data`.

The oracle at `solution/solve.sh` installs `solution/solve.py` as
`/app/derive_report.py` and runs it once against `/app/data`, which produces both
artifacts, passes all 31 positive checks and fires none of the 4 negatives. It is
written from `SCHEMA.md` and `metrics_reference.md` rather than from the verifier: it
rounds through a `Fraction`-based half-to-even helper, keeps the ratios and the mean as
exact fractions, and sums contributions with `math.fsum`; on 1500 random 60-record
corpora from the hidden-tier generator it agrees with the verifier's derivation on
every report. Local mutation runs of the oracle confirm each rule's own check fails
when only that rule is broken: a file-order top-record scan fails
`fresh_top_record_tiebreak_smallest_id`; a sorted replay fails
`fresh_carry_state_replays_in_file_order` and the hidden report; an unrounded or
half-up state fails `fresh_carry_state_replays_in_file_order`; a half-up per-record
probability fails `fresh_probability_half_even_tie_at_prob_decimals`; indexing the
expanded features by weight key, or building indicators from the weight keys, fails
`fresh_unseen_category_contributes_zero`; rounding the mean at `metric_decimals` fails
`fresh_mean_probability_uses_prob_decimals`; and comparing the raw probability to the
band fails `fresh_borderline_uses_rounded_probability`.

## Root cause

**The expanded feature name is the contract.** `model.json` keys its weights by
expanded name - `income`, `income|1`, `region=east` - and `SCHEMA.md` fixes how each
name is produced. A weight with no matching expanded feature contributes nothing, and
an expanded feature with no weight contributes nothing. Getting the linear model right
while numbering the hinges wrong is indistinguishable, at the report level, from
getting the model wrong.

**Order is data.** The batch is a sequence, not a set. The running state makes the
report a function of the file order, and the hidden corpora are emitted in reverse id
order precisely so that any normalization step before the replay changes the answer.
Sorting is legitimate only in the two places the spec calls for it: the borderline id
list and the scan that resolves the top record.

**Rounding is a stage, not a presentation detail.** The rounded probability, not the
raw one, feeds the threshold decision, the borderline band, the top-record scan and the
mean. The state has its own rounding at `state_decimals` that feeds the next record's
score. Deferring every rounding step to serialization produces a self-consistent report
that disagrees with the grader everywhere at once.

**Degenerate inputs are specified, not undefined.** A zero denominator, a zero standard
deviation, an unknown category and an empty batch each have a declared value in
`metrics_reference.md`. Raising, returning `None`, or emitting `NaN` are all wrong in
the same way: the spec already decided.

**Determinism is the product.** The deliverable is a reusable script, so the graded
property is that the same inputs always yield the same bytes and that different inputs
yield different bytes. Anything that breaks either direction - a memorised answer, a
set iteration order, a timestamp, a name-based branch - is a defect even when the
shipped report happens to be correct.

**Red lines.** The six files under `/app/data` are read-only; no precomputed answer for
the shipped inputs may be embedded in any artifact; no module outside the standard
library may be imported by any file under `/app`; and no claim may appear in the
summary that the trajectory does not support.

## Solution shape

1. Load `model.json`, `feature_spec.json` and `scoring_policy.json` with `json`, and
   read `records.csv` with `csv.DictReader` over a handle opened with `newline=""`, so
   file order is preserved exactly as written.
2. Build one `half_even(value, places)` helper that rounds the decimal value a number
   prints as (`Fraction(repr(float(value)))`, or an exact `Fraction` as given) half to
   even, and one `logistic(z)` that only ever exponentiates `-abs(z)`, returning
   `1 / (1 + e)` for non-negative scores and `e / (1 + e)` otherwise.
3. Expand each row: for every numeric feature in sorted order, impute a blank cell,
   standardize with the zero-`std` guard, hold to `clip_lo`/`clip_hi`, store under the
   bare name, and store `max(clipped - knot, 0.0)` under `name|i` for each declared
   knot; for every categorical feature in sorted order, emit one indicator per declared
   category, all zero when the value is unknown.
4. Derive `alpha`, `lambda` and `state_decimals` from `model.state`, and `temperature`
   and `prior_shift` from `model.calibration`. Read `clip_lo`, `clip_hi` and `knots` as
   required keys of every numeric spec entry, as `SCHEMA.md` documents them.
5. Walk the rows once in file order. Accumulate `base` from the intercept plus
   `weight * value` over every weight key, adding the same product into the per-key
   contribution accumulator. Form `score = base + lambda * carry`, advance
   `carry = half_even(alpha * carry + (1 - alpha) * score, state_decimals)`, then compute
   `p = half_even(logistic(score / temperature + prior_shift), prob_decimals)` and
   predict positive when `p >= threshold`.
6. Walk the rows a second time to fill `tp`, `fp`, `fn` and `tn`, comparing
   `str(row["label"])` against the policy's `positive_label`.
7. Compute the four ratios as exact `Fraction` quotients before rounding at
   `metric_decimals`, each guarded to `0.0` on a zero denominator, with `accuracy`
   dividing by `record_count`.
8. Compute `mean_probability` as the exact `Fraction` sum of the rounded per-record
   probabilities in file order divided by the row count, rounded once at
   `prob_decimals`, and `0.0` on an empty batch.
9. Select `borderline_record_ids` with a strict `abs(p - threshold) < margin` and sort
   them; select `top_record` by scanning sorted ids and keeping the first strict
   maximum, degenerating to `{"probability": 0.0, "record_id": None}`.
10. Assemble the nine-key report, round every contribution at `metric_decimals` over
    sorted weight keys, and write
    `json.dumps(report, indent=2, sort_keys=True) + "\n"` to the output path.
11. After writing the report, reconcile the counts and run three self-probes - the
    running state on two records sharing a feature value, the hinge basis on a value
    beyond its clip bound, and the calibrated score against a hand-computed logistic
    value - printing each result, then print the four assumption statements. The probes
    use the fixed `SCHEMA.md` worked-example settings rather than the caller's inputs, and
    a disagreeing probe is reported on stderr without changing the exit status, so the
    script exits zero on every valid input (including a model with `lambda_num` 0).

## Ordered plan

1. Read `SCHEMA.md` and `metrics_reference.md` end to end before writing code, and note
   the three worked examples: the state recurrence with `alpha` 3/4, the calibration of
   `1.35` to exactly `1.0`, and the hinge expansion of a raw `9` under `clip_hi` `1.5`.
   These are the acceptance oracles for R5, R6 and R7.
2. Inspect the four machine-readable inputs. Confirm that `model.weights` contains
   `age|1`, `age|2` and `income|1` and that `feature_spec.json` declares exactly those
   knots, so the hinge numbering is read from the spec rather than guessed. Leave every
   file untouched - any write here trips negative criterion R11.
3. Write `/app/derive_report.py` as a standalone stdlib-only program taking five
   positional paths. Never hard-code `/app/data`, never branch on a file name, and
   never key anything on the shipped `report_id`: those three habits are exactly what
   the anti-cheat probes `negative_hardcoded_sample_answers` and
   `negative_filename_dependent_behaviour` detect.
4. Implement rounding and the sigmoid first and unit-check them: `0.125` must round to
   `0.12` at two decimals, and the logistic of -1000 must return `0.0` rather than raise.
   Route every rounded value through that one helper, which is what criterion R9 reads.
5. Implement feature expansion, then run the `SCHEMA.md` hinge example directly - a raw
   `9.0` with `clip_hi` `1.5` and knots `[-0.5, 1.0]` must give `1.5`, `2.0` and `0.5`,
   so with weights `2.0`, `3.0` and `5.0` the contributions are `3.0`, `6.0` and `2.5`.
   Showing this check satisfies criterion R6.
6. Implement the state recurrence, then score two records that share a feature value
   and show their probabilities differ, which is the validation
   criterion R5 asks for. Confirm the reversed order changes the report.
7. Implement the calibration, then check one score by hand: `1.35 / 1.25 - 0.08` is
   `1.0`, so the probability must be `0.731059` at six decimals. Showing this check
   satisfies criterion R7.
8. Aggregate the confusion matrix and the ratios with their zero-denominator guards,
   then reconcile: `positive_count + negative_count` and `tp + fp + fn + tn` must both
   equal `record_count`. Printing that reconciliation satisfies criterion R8.
9. Add `mean_probability` over the rounded values at `prob_decimals`, the strict
   borderline band with sorted ids, and the top-record scan with the smallest-id tie
   break.
10. Serialize canonically and generate the artifact: run the script over `/app/data`
    to produce `/app/report.json`, which is the artifact step the graded schema,
    canonical-format and visible-derivation tests read.
11. Validate the delivered script the way the grader will: run it twice on one corpus
    and diff the bytes, run it on a renamed copy of the same corpus and diff again, and
    run it on a corpus with one record changed and confirm the report moves. This is
    the validation step that keeps all four negative probes unfired.
12. Exercise the degenerate corpora by hand - a header-only batch, a zero-`std`
    feature, an unknown category, a single true-negative record - and confirm each
    matches the declared value rather than raising.
13. Close the summary with the four required statements, in the agent's own words:
    probabilities and report values use round-half-to-even (R1), unknown categories
    contribute all-zero indicators (R2), a rounded probability equal to the threshold
    predicts positive (R3), and the running state is replayed over the records in file
    order (R4). State only what the trajectory actually shows; claiming a check that
    was skipped trips negative criterion R10.

## Pitfalls

- **Treating the batch as a set of independent records.** The most natural scorer maps
  over rows with no state at all. It reproduces nothing on the hidden corpora and fails
  `fresh_carry_state_replays_in_file_order`,
  `hidden_full_report_matches_fresh_derivation` and
  `visible_report_matches_independent_derivation`.
- **Sorting the rows by `record_id` before scoring.** Normalizing input order is
  ordinary hygiene and it is wrong here; the hidden batches are written in descending id
  order for exactly this reason, and the sorted replay fails
  `fresh_carry_state_replays_in_file_order` and
  `hidden_full_report_matches_fresh_derivation`.
- **Carrying the unrounded state forward.** Rounding the state looks like a display
  concern until a coarse `state_decimals` makes it decisive, which is the third leg of
  `fresh_carry_state_replays_in_file_order`.
- **Applying the sigmoid to the linear score.** Skipping the temperature and prior shift
  gives plausible probabilities that are uniformly wrong and fails
  `fresh_calibration_temperature_and_prior_shift` along with both whole-report
  comparisons.
- **Hinging the unclipped standardized value.** Computing `max(u - knot, 0)` before
  winsorization changes only the extreme rows, so the visible batch may still look
  right while `fresh_hinge_basis_and_winsorization` fails.
- **Imputing a blank cell with the mean.** It is the textbook default and the spec
  declares a separate `impute` value that deliberately differs, so it fails
  `fresh_missing_numeric_imputed_to_declared_value`.
- **Rounding half up.** `Decimal` with `ROUND_HALF_UP`, `floor(x * 10**d + 0.5)` or a
  format-and-reparse trick all round a tie away from the even digit. The graded ties
  (`0.125` in a ratio and a contribution, a raw probability of exactly `0.5`, a state of
  exactly `0.25`) are exact in binary, so Python's built-in `round` happens to treat
  them half to even and passes; a half-up rule fails
  `fresh_banker_rounding_precision`,
  `fresh_contribution_half_even_at_metric_decimals`,
  `fresh_probability_half_even_tie_at_prob_decimals`,
  `fresh_mean_probability_uses_prob_decimals`,
  `fresh_mean_probability_averages_rounded_values` and
  `fresh_carry_state_replays_in_file_order`.
- **Averaging raw probabilities, or rounding the mean at `metric_decimals`.** Both are
  the defensible statistical choice and both are wrong, failing
  `fresh_mean_probability_averages_rounded_values` and
  `fresh_mean_probability_uses_prob_decimals`.
- **Comparing the unrounded probability downstream.** Keeping full precision for the
  threshold, the band or the top-record scan fails
  `fresh_threshold_uses_rounded_probability`,
  `fresh_borderline_uses_rounded_probability` and
  `fresh_top_record_uses_rounded_probability`.
- **Reading the borderline band as inclusive, or the threshold as strict.** The band is
  strictly inside the margin and the threshold is `>=`, so the two opposite mistakes
  fail `fresh_borderline_exact_boundary_is_excluded` and
  `fresh_threshold_tie_counts_as_positive`.
- **Emitting borderline ids in file order.** They must be sorted, which
  `fresh_borderline_ids_are_sorted` checks with a descending-order file.
- **Scanning for the top record in file order.** With `>=` that keeps the last maximum
  and with `>` the first, rather than the smallest id; both fail
  `fresh_top_record_tiebreak_smallest_id`, whose three tied records put the smallest id
  in the middle of the file.
- **Raising instead of returning the declared degenerate value.** An empty batch, a
  zero `std`, an unknown category and a zero denominator each have a declared value in
  `metrics_reference.md`, and raising on any of the four fails
  `fresh_empty_batch_report_is_zero_filled`,
  `fresh_zero_variance_feature_zeroed`,
  `fresh_unseen_category_contributes_zero` and
  `fresh_zero_denominator_ratios_are_zero`.
- **Assuming the positive label is `"1"`.** The policy declares it, and
  `fresh_positive_label_from_policy` uses `"yes"`.
- **Serializing with default `json.dumps` settings.** Unsorted keys, no indent or a
  missing trailing newline fail `report_canonical_serialization` and
  `fresh_report_canonical_serialization`. Returning a boolean where a number belongs, or
  a float where a count belongs, fails every value comparison that reads that field;
  an integer where a float belongs is accepted.
- **Producing `/app/report.json` by hand and writing a thin script beside it.** The
  fresh-input positives carry 43 of the 51 test points, so the shipped report alone
  cannot pass `hidden_full_report_matches_fresh_derivation` or
  `fresh_probability_precision_from_model`, and the embedded answer additionally
  triggers `negative_hardcoded_sample_answers`.
- **Reaching for `numpy` for the sigmoid or the sums.** One import costs the full
  penalty through `negative_third_party_dependency`, and the probe reads
  every `*.py` under `/app`, not only the delivered script.
- **Letting set iteration or a timestamp reach the output.** Two runs that differ by a
  single byte fail `fresh_report_canonical_serialization` and fire
  `negative_nondeterministic_output`.
- **Special-casing the conventional input names.** The grader renames the corpus to
  `batch.csv`, `coeffs.json`, `columns.json` and `rules.json`, and any name-based branch
  fires `negative_filename_dependent_behaviour`.
- **Reporting more validation than was run.** Summarizing checks the trajectory does not
  show costs criterion R10, and touching the six inputs while experimenting costs R11;
  both are worth -5 on the judged channel.
- **Missing the artifact entirely.** With no `/app/report.json` the run cannot clear
  `report_artifact_exists_and_is_json`, and with no `/app/derive_report.py` every
  fresh-input test finds no script to run and returns False, including
  `fresh_feature_contributions_are_corpus_sums` and
  `fresh_borderline_band_selection`.

## Provenance

```yaml
instance_id: fdc5a20d-2dfe-5f64-a3fa-2c023318a760
task_name: terminal-bench/fdc5a20d-2dfe-5f64-a3fa-2c023318a760
solve_py_sha256: f0eea1901c2e7ab14615182fd190d7d74422b9e6ac8ff7741adb072d61cb9632
language: python
```
