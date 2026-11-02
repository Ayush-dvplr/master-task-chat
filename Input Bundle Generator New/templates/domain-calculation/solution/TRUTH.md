# TRUTH.md - {{BUNDLE_NAME}}

## Defect

There is no broken program to repair. `/app/data` holds ten data files (about
twenty-five thousand lines: twelve thousand transactions, 2,500 customers, 2,400 sites,
a 2,160-cell department-by-category multiplier table, daily FX rates and a six-year
calendar) and a written contract at `/app/data/schema.md`, and the deliverable is a reusable derivation script that
turns them into nine exact JSON artifacts. The whole difficulty is arithmetic order: three
money figures per transaction, each defined as a chain of steps where every step rounds
half up to whole USD cents *before the next step consumes it*. Reorder two steps and every
figure in every artifact moves by a few cents - enough to fail every exact comparison,
small enough that a spot check looks fine. The rates, thresholds, discount codes, and
transaction corpus are specific to this task instance, so nothing below can be
recalled from training, and the grader reruns the delivered script against a corpus it
generates itself from the shipped reference tables. Every transaction needs seven other
files (customer, discount code, site, tax rule, multiplier cell, dated FX rate, calendar
period), so deleting any single input drops the reference solution below a third of the
test channel.

0. (focal) Three lookups are keyed more narrowly than they look. The FX rate is chosen
   by `(posted_date, currency)`, not by currency alone. The multiplier is chosen by
   `(department, category)`, not by department. The tax rate is the site override when
   one exists, then the region override, then the default; ignoring the site layer
   misprices the roughly nine hundred overridden sites.

1. (focal) `adjusted_net_cents` is a five-step pipeline whose order is stated once and is
   not negotiable: start from `gross_cents + tax_cents`; apply the customer's discount as a
   `(10000 + discount_bps) / 10000` multiplier and round; apply the department's
   `base_multiplier` to that discounted subtotal and round; *then* add the site's
   `site_adjustment_cents`; and only then take the larger of the result and
   `minimum_net_cents`. The site adjustment lands after the department multiplier, not
   before, so it is never scaled. The floor is last of all, so it clamps the finished
   number rather than an intermediate. Both of those are the natural places to get it
   wrong, and `visible_summary_matches_reference` compares the whole document.
2. (focal) Currency conversion happens per field, not per transaction. `amount_cents` and
   `tax_basis_cents` are each multiplied by `rate_to_usd_basis_points`, divided by 10000,
   and rounded half up *independently*. Converting their sum once and splitting it
   afterwards produces a different pair of numbers whenever both roundings would have gone
   the same way, and the seeded corpus contains those rows deliberately.
   `rounding_credits_fx_discounts_and_clamp` is built on exactly this.
3. (focal) `policy_audit.json`'s `department_multipliers` values are **strings**, and they
   must be the identical text that appears in the `rate_table.csv` cell, nested by
   department and then category. A cell reading `1.050` is emitted as `"1.050"`, not
   `"1.05"`, and `1` stays `"1"`. Reading the column as a float and stringifying it silently normalises trailing
   zeros away; reading it as `Decimal` and stringifying preserves them, which is why the
   reference carries the multiplier as a `Decimal` from the moment it is parsed.
   `policy_audit_matches_reference` reads these as literal strings.
4. (focal) The two alert shapes are different and both are called "variance". Summary
   alerts are a *list* of per-site objects keyed `site` and `delta_cents`, one for every
   site whose entry in `site_totals` - which accumulates *adjusted* net - departs from the
   sum of that site's *gross* amounts by at least `variance_alert_cents`, emitted in sorted
   site order. Bucket alerts, in the region and segment files, are a list holding *at most
   one* object keyed `name` and `delta_cents`, raised when that bucket's
   `adjusted_net_cents` departs from its `gross_cents` by the same threshold. Same
   threshold, same subtraction, different key name, different cardinality.
5. (drift) `largest_transaction` selects on the **converted** amount, not the raw
   `amount_cents` from the CSV, and it breaks ties on the **lowest** `txn_id`. The
   experienced instinct is to sort descending and take the head, which breaks ties on
   whichever row the sort happened to leave first, and to compare the pre-conversion
   column because it is the one the file actually contains. Both readings produce a
   plausible `txn_id` and fail `visible_summary_matches_reference` on a single key.
6. (trap) A transaction can raise two quality issues at once. The posting-lag check and the
   calendar-membership check are independent `if` statements, not branches of the same
   decision, so a late transaction posted on a date missing from `calendar.csv` contributes
   two entries to `quality_issues` and two to `quality_issue_count`. The list is sorted as
   strings before serialization, and a transaction whose posted date is absent from the
   calendar still contributes to `period_totals` - under the period key `unknown`.
7. (trap) Region files are capitalised and segment files are not. The four region artifacts
   are `region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`,
   while the segments are `segment_commercial.json` and `segment_public.json`. The names
   come from `required_regions` and `required_segments` in `thresholds.json` and every one
   of the six files is written on every run, including buckets no transaction reached.

The reference is authored in Python (Python 3.12, standard library only, a
{{TRUTH_SOLVE_PY_LINES}}-line derivation module exposing `derive(data_dir)` and
`write_artifacts(data_dir, out_dir)`) with a Bash oracle dispatcher (`solve.sh`) that
installs it at `/app/out/derive_report.py` and runs it against `/app/data` and `/app/out`.
A deterministic channel observes the nine artifacts and reruns the delivered script against
a reseeded corpus (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the derivation trajectory
(Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the prose above
 -  read them from those files, or from the lists below, which mirror them.

Out of bounds: writing the artifact values as literals instead of deriving them
(`negative_hardcoded_sample_answers`); omitting or emptying the audit, quality,
region, or segment documents to avoid the harder arithmetic
(`negative_missing_substantive_sections`); reading anything under `tests/`,
`/logs/`, or any reward file while solving
(`negative_reads_tests_or_reward_files`,
`no_network_dependencies_or_verifier_reads`); importing a third-party package or
touching the network (`negative_external_dependency_or_network`); and looking
the corpus up online - it is specific to this instance and exists nowhere else.

## Load-bearing work

{{TRUTH_ARTIFACT_COUNT}} artifacts are collected, and every one of them is graded:

{{TRUTH_ARTIFACT_LIST}}

- `/app/out/derive_report.py` (new) - the deliverable, a stdlib-only script runnable as
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR` that exits 2 with a usage line when
  given the wrong number of arguments. It is read as source by the anti-cheat tests and
  re-executed against a fresh corpus by
  `hidden_seeded_outputs_match_reference`, so it is both the program and a graded
  artifact.
- `/app/out/summary.json` (new) - `report_id` carried from `policy.json`,
  `transaction_count`, the three money totals, the four sorted total maps
  `department_totals`, `site_totals`, `category_units`, `period_totals`,
  `largest_transaction`, `posting_lag_days` with `max` and a two-decimal `average`, and the
  per-site `alerts` list.
- `/app/out/policy_audit.json` (new) - the rule tables echoed back: the sorted region
  override map, the sorted discount-code map, the department multipliers as verbatim
  strings, and the two integer thresholds.
- `/app/out/data_quality.json` (new) - `input_file_count`, `transaction_count`,
  `customer_count`, `region_count`, `quality_issue_count`, and the sorted `quality_issues`
  strings.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`,
  `region_East.json` (new) - one per required region, always all four.
- `/app/out/segment_commercial.json`, `segment_public.json` (new) - one per required
  segment, always both. Each bucket file carries `name`, `transaction_count`, the three
  money totals, sorted `department_totals` and `category_units`, the sorted `customers`
  list, and the at-most-one-element `alerts` list.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows
the shape of the work, not the text to type.

Out of bounds by design: artifacts whose values are tied to the shipped transaction corpus;
a script that only works when the input directory is `/app/data`; a script an unprivileged
user cannot execute; any artifact missing its trailing newline or written with unsorted
keys; and any read of the grading machinery.

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

Note that the six bucket artifacts are graded by six separate tests rather than one, so a
single misplaced rounding step costs six independent weights at once rather than one.
`hidden_seeded_outputs_match_reference` rebuilds the corpus from
`EVAL_SEED = {{EVAL_SEED}}` - distinct from the visible `SAMPLE_SEED = {{SAMPLE_SEED}}` and
the labelled `CHALLENGE_SEED = {{CHALLENGE_SEED}}` - and
`reusable_script_writable_by_unprivileged_submission_style` runs the delivered script
as a non-root user, so file modes matter as much as arithmetic. The oracle expectation is
that running `solution/solve.sh` inside the container drives every positive Channel A test
to pass and holds every negative test in its failing state.

## Root cause

**Rounding is a sequence, not a final step.** The contract says "every step rounds half up
to whole USD cents before the next step uses it", which means the discount multiplier is
applied to an integer and produces an integer, and the department multiplier is applied to
*that* integer. Carrying full `Decimal` precision through the chain and rounding once at
the end is more accurate and is wrong: it produces different numbers on any transaction
where two intermediate roundings would have compounded. Accuracy is not the objective;
reproducing the specified computation is.

**Half-up is explicit and Python's default is not.** `Decimal.quantize` without a rounding
argument uses `ROUND_HALF_EVEN`. Every quantization in this task - the two FX conversions,
the tax computation, the discount step, the department step - has to name
`ROUND_HALF_UP`. Floats are excluded entirely from the money path; `Decimal(amount) *
Decimal(rate) / Decimal(10000)` keeps the arithmetic exact until the deliberate rounding.

**Basis points are per-ten-thousand and appear in three unrelated places.** FX rates are
basis points over 10000. Tax rates are basis points over 10000, taken from
`region_overrides_basis_points` when the transaction's region has an override and from
`default_tax_rate_basis_points` when it does not - and the lookup key is the region *name*
from `regions.csv`, not the site code. Discounts are basis points too, but they enter as
`(10000 + discount_bps) / 10000`, so a negative discount code reduces the subtotal and a
positive one increases it.

**Joins have a direction.** A transaction names a `customer_id` and a `site`. The customer
supplies the `segment` and the `discount_code`; the site supplies the `region_name` and
the `site_adjustment_cents`. The region name - not the site - keys the tax override and
selects the region bucket. Getting the site and the region confused produces a report that
balances internally and disagrees with the reference everywhere.

**Periods come from the posted date, lags come from both dates.** The reporting period is
`calendar.csv`'s `period` for the `posted_date`; posting lag is `posted_date` minus
`service_date` in days, using `date.fromisoformat` rather than string arithmetic. The lag
feeds `posting_lag_days.max`, the two-decimal `average`, and the first quality check.

**Determinism requirements.** Every map in every artifact is emitted through
`dict(sorted(...))`, the `customers` array through `sorted()`, and `quality_issues` through
`sorted()` on the message strings. Serialization is `json.dumps(..., indent=2,
sort_keys=True)` plus an explicit trailing newline. Nothing carries a timestamp, a `uuid`,
or a random value.

**Red lines.** No hardcoded answers; no omitted or hollowed-out artifacts; no reads of
`tests/`, `/logs/`, or reward files; no third-party imports and no network; no floats in
the money path; no output whose bytes vary between runs; no online lookup.

## Solution shape

1. Load the ten inputs from the directory given on the command line: `policy.json`,
   `thresholds.json`, `tax_rules.json`, and `discount_rules.json` as JSON; `transactions.csv`
   as a row list; and `customers.csv`, `rate_table.csv`, `fx_rates.csv`, `regions.csv`, and
   `calendar.csv` as dictionaries keyed by their identifier columns (the multiplier table
   by `(department, category)`, the FX table by `(date, currency)`). Keep each
   `base_multiplier` cell's text for the audit and parse it as `Decimal` for the
   arithmetic; parse the FX and discount values as `int`.
2. Pre-create every required region and segment bucket from `thresholds["required_regions"]`
   and `thresholds["required_segments"]` in their zero state, so a bucket no transaction
   reaches still serializes with zeroes and empty maps.
3. For each transaction, resolve the customer and the site, read the region name from the
   site and the segment from the customer, and convert `amount_cents` and
   `tax_basis_cents` to USD cents independently through the basis-point FX rate.
4. Compute tax from the converted basis and the applicable basis points, then walk the
   five-step adjusted-net chain in order, rounding half up at each step, adding the site
   adjustment after the department multiplier and applying the `minimum_net_cents` floor
   last.
5. Compute the posting lag from the two ISO dates, append a quality issue when it exceeds
   the configured maximum, append a second, independent quality issue when the posted date
   is absent from the calendar, and resolve the period - falling back to `unknown`.
6. Accumulate: the three running totals; the four summary maps, where the three money maps
   take *adjusted* net and `category_units` takes raw units; the largest-transaction
   candidate on converted amount with the lowest-`txn_id` tiebreak; and both the region and
   the segment bucket for this transaction, appending the customer id if not already
   present.
7. After the loop, compute the per-site variance alerts by comparing each site's adjusted
   total to the sum of that site's gross amounts in sorted site order, then assemble
   `summary.json`, `policy_audit.json`, and `data_quality.json`.
8. Finalize each bucket - raise its single alert if its adjusted net departs from its gross
   by the threshold, sort its two maps and its customer list - and write all nine artifacts
   with sorted keys, a two-space indent, and a trailing newline.

## Ordered plan

1. Read `schema.md` first and completely, then open every input file and match each
   contract sentence to the columns that back it. Rubric R1 credits exactly this:
   inspecting the flat input corpus and the schema contract before producing artifacts.
2. Transcribe the adjusted-net chain into five explicit lines of pseudocode with the
   rounding marked at each step, and confirm against the contract that the site adjustment
   is after the multiplier and the floor is last. This is the single highest-leverage
   minute in the task.
3. Implement the conversion and rounding helpers and check them by hand on one transaction,
   writing out gross, tax, discounted, multiplied, adjusted as five separate numbers.
   Rubric R3 credits handling joins, signed credits, cents, currency conversion, discounts,
   and half-up rounding as explicit domain invariants, and rubric R2 credits deriving the
   artifacts from transaction-level calculations shown or executed during the session.
4. Build the joins and confirm the direction of each one by printing a single transaction's
   resolved customer, segment, site, region name, discount code, and site adjustment side
   by side.
5. Run the script against `/app/data` and check the internal identities before comparing
   anything: the region buckets' `transaction_count` must sum to the summary's, and so must
   the segment buckets'; each bucket's three money totals must sum to the summary's across
   regions and across segments independently. Rubric R8 credits explaining or recording the
   checks that support the final report values.
6. Test the edges deliberately. Feed a transaction whose posted date is not in
   `calendar.csv` and confirm two things at once - an `unknown` entry in `period_totals`
   and a quality issue. Feed one whose computed net falls below `minimum_net_cents` and
   confirm the clamp fires last. Rubric R4 credits validating at least one edge case beyond
   the visible happy path, and rubric R5 credits accounting for locale, date, and row-order
   invariants.
7. Run the script with an explicit input and output directory pair that is not
   `/app/data` and `/app/out`, and make the file executable and world-readable so an
   unprivileged user can run it. Rubric R6 credits basing the derivation on local flat
   inputs through visible standard-library operations, and rubric R7 credits writing every
   requested artifact through deterministic serialization steps visible in the trajectory.
8. Run twice into two clean directories, diff all nine artifacts byte for byte, and close
   with a summary of what was derived and where it was written - rubric R10 credits exactly
   that closing summary.

## Pitfalls

- **Adding the site adjustment before the department multiplier.** It scales the adjustment
  and shifts every transaction at that site. The contract states the order explicitly
  because this is the reordering people make.
- **Applying the `minimum_net_cents` floor before the site adjustment.** The floor is last
  of all, so a negative site adjustment can legitimately be clamped away - but only after
  it has been applied.
- **Rounding once at the end.** More precise, and wrong. Each of the five steps rounds
  before the next reads it.
- **Letting `ROUND_HALF_EVEN` in by omission.** Every `quantize` call needs
  `rounding=ROUND_HALF_UP` named explicitly.
- **Converting the transaction total instead of each field.** `amount_cents` and
  `tax_basis_cents` are converted and rounded separately.
- **Emitting `department_multipliers` as numbers.** They are strings, and they must
  preserve the exact text of the CSV cell - `"1.50"` stays `"1.50"`. Parsing the column as
  a float destroys this before it can be recovered.
- **Keying the tax override on the site code.** The override map is keyed by region name.
  The site is only a lookup step on the way there.
- **Using the same alert key in both places.** Summary alerts use `site`; bucket alerts use
  `name`. Reusing one shape for both fails whichever test reads the other.
- **Emitting more than one bucket alert.** A bucket's `alerts` is a list of at most one
  object, or empty. Appending per contributing site to a region file is wrong.
- **Comparing the wrong pair for the variance.** Both alerts subtract gross from adjusted
  - the summary version does it per site against `site_totals`, which already holds
  adjusted net.
- **Selecting `largest_transaction` on the raw column, or breaking ties the wrong way.**
  Converted amount, lowest `txn_id`.
- **Treating the two quality checks as alternatives.** They are independent; one
  transaction can raise both.
- **Dropping a transaction whose posted date is missing from the calendar.** It still
  counts, still contributes money, and lands under the period key `unknown`.
- **Lowercasing the region filenames.** `region_North.json`, not `region_north.json`. The
  segments really are lowercase, which makes the inconsistency easy to smooth over.
- **Omitting a bucket with no transactions.** All four regions and both segments are
  written every run.
- **`round()` on the posting-lag average.** It is a float rounded to two decimal places,
  which is the one place in this task where a float is correct - and where reaching for
  `Decimal` produces a value that does not serialize the same way.
- **Forgetting the trailing newline, or the sorted keys.**
  `canonical_serialization_and_sorted_keys` reads the bytes.
- **Opening anything under `tests/` "just to check".** It fires
  `negative_reads_tests_or_reward_files` and is graded again by rubric R9 as
  bypassing derivation.

## Provenance

{{TRUTH_PROVENANCE_BLOCK}}
