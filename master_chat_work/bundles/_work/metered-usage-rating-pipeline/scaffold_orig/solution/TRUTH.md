# TRUTH.md - metered-usage-rating-pipeline

## Defect

Nothing is broken here - everything is absent. `/app/data` holds eleven data files
(about forty-five thousand lines in four formats) plus `schema.md`, and no code. The
deliverable is a reusable transform that turns them into fourteen exact artifacts. No
file can be skipped: a transaction reaches its region, currency, rate and channel only
through a chain of lookups that crosses every reference file, and deleting any one input
drops the reference solution below half the test channel. The grader also reruns the delivered script on a copy of the
data with the sales and FX rows reordered and one currency's rates changed, so every
figure has to fall out of the rules rather than out of the shipped sample. Identifiers,
amounts, currencies and row counts are specific to this task instance, so
nothing below can be recalled from training.

0. (focal) The lookup chain. Sales, refunds and legacy rows take their region from the
   shipping warehouse: `warehouse` -> its `postal_code` in `inventory.csv` -> the prefix
   before `-` -> `regions.csv`. Adjustments have no warehouse and take the customer's
   home `postal_code` from `customers.csv` instead. A blank currency resolves to that
   region's `default_currency`, and only then can the `(date, currency)` rate be found in
   `fx_rates.csv`. Taking the region from the customer for every row, or converting a
   blank currency as USD, moves records between regions and between cents totals.
1. (focal) Four input formats feed one record stream and each carries its sign convention
   in a different place. `sales.csv` amounts are `quantity * unit_price`, always positive.
   `refunds.csv` amounts are `refund_amount` forced negative regardless of how the column
   is written. `adjustments.jsonl` arrives pre-multiplied as signed `amount_cents`.
   `legacy.txt` is pipe-delimited with optional `#` comment lines, and its sign depends on
   the `kind` token: `refund` and `credit` are forced negative, `sale` and `fee` forced
   positive. Getting three of the four right produces a summary that is close and wrong,
   and `visible_summary_exact` compares the whole document.
2. (focal) Currency conversion is a single `Decimal` expression, not a sequence of
   roundings. The amount, the FX rate, and the factor of 100 are multiplied together and
   the *product* is quantized once with `ROUND_HALF_UP`. Converting to USD and then to
   cents, or quantizing before multiplying, or letting a float into the chain, shifts
   individual records by one cent - invisible per row, fatal once summed across a bucket.
   `adjustments.jsonl` is the sharp case: it arrives in cents, so it has to be divided by
   100 back into currency units and pushed through the same conversion, not passed through
   as if it were already USD.
3. (focal) `net_units` is not the signed amount and not the raw quantity. A `sale`
   contributes `+quantity`, a `refund` contributes `-quantity`, and every other kind  - 
   `fee`, `credit`, anything the corpus invents - contributes exactly zero units even
   though it contributes its full cents to `total_usd_cents`. The same rule governs
   `net_units` in `product_summary.json` and in all nine region and segment files, so one
   misreading fails `product_summary_exact`, `region_outputs_exact`, and
   `segment_outputs_exact` together.
4. (focal) `normalized.jsonl` and the JSON artifacts use two different serializations, on
   purpose. The JSONL rows are compact - `sort_keys=True` with `(",", ":")` separators, one
   record per line, no spaces - and the rows are ordered by `event_id` as a string, not by
   date and not in file order. The twelve `.json` files are `sort_keys=True` with a
   two-space indent and a trailing newline.
   `output_format_is_canonical_and_deterministic` checks the JSONL line-for-line
   against compact dumps and separately asserts every `.json` artifact ends in a newline.
5. (drift) `source`, `records_by_source` and `skipped_by_source` use the input *file
   names*, extension included - `sales.csv`, `refunds.csv`, `adjustments.jsonl`,
   `legacy.txt` - as `schema.md` states. Writing bare stems (`sales`) is the natural
   slip, and `data_quality_exact` and every normalized-record comparison catch it.
6. (trap) Malformed rows are spread through every transaction file: unknown customers,
   SKUs, warehouses and terminals, quantities written as `two` or `1.5`, an
   `amount_cents` of `"n/a"`, and impossible dates such as month 13, which have no FX
   row. Each is skipped and counted per source. Dates past the end of `calendar.csv`
   are not malformed: they keep their rate and get fiscal week `unknown`.
7. (trap) `inventory.csv` has one row per `(sku, warehouse)` pair, so a SKU stocked in
   three warehouses appears three times. `on_hand` and `reorder_point` in
   `product_summary.json` are the *sums* across warehouses. Building the inventory map
   with a plain dict assignment keeps only the last row and silently understates every
   multi-warehouse product.

The reference is authored in Python (Python 3.12, standard library only, a
242-line driver that writes and then executes the transform) with a
Bash oracle dispatcher (`solve.sh`) that runs it against `/app/data` and `/app/out`. A
deterministic channel observes the fourteen artifacts and reruns the delivered script
against relocated and reordered corpora (Channel A, `tests/test_output.py`, weighted by its
`criteria.<name>(weight=W)` registrations); a judged rubric channel grades the derivation
trajectory (Channel B, `tests/judge.toml`). Counts and weights are not mirrored into the
prose above - read them from those files, or from the lists below, which mirror them.

Out of bounds: embedding the visible records or the visible outputs as literals in
`transform.py` (`negative_embedded_visible_records`,
`negative_hardcoded_sample_answers`); hardcoding `/app/data` or `/app/out` so
the script cannot be pointed elsewhere
(`reusable_transform_regenerates_visible_outputs_elsewhere`); shelling out to `awk`,
`sed`, `sort`, or a subprocess to do the work, or importing anything off PyPI
(`negative_network_dependency_or_shell_cheat`,
`transform_avoids_network_dependencies_and_shelling_out`); writing anywhere outside
the output directory the script was given
(`transform_does_not_write_outside_output_dir`); letting a timestamp, a `uuid`, an
unordered set, or a dict iteration order into an artifact
(`negative_nondeterministic_output`); and looking the corpus up online - it is
generated for this instance and exists nowhere else.

## Load-bearing work

14 artifacts are collected, and every one of them is graded:

- `/app/out/transform.py`
- `/app/out/normalized.jsonl`
- `/app/out/summary.json`
- `/app/out/data_quality.json`
- `/app/out/product_summary.json`
- `/app/out/region_central.json`
- `/app/out/region_east.json`
- `/app/out/region_north.json`
- `/app/out/region_south.json`
- `/app/out/region_west.json`
- `/app/out/segment_consumer.json`
- `/app/out/segment_corporate.json`
- `/app/out/segment_enterprise.json`
- `/app/out/segment_smb.json`

- `/app/out/transform.py` (new) - the deliverable itself, an executable stdlib-only script
  runnable as `python3 /app/out/transform.py DATA_DIR OUT_DIR` and falling back to
  `/app/data` and `/app/out` when invoked bare. It is read as source by the anti-cheat
  tests and re-executed against fresh corpora by the correctness tests, so it is both the
  program and a graded artifact.
- `/app/out/normalized.jsonl` (new) - one compact JSON object per accepted transaction,
  sorted by `event_id`, carrying the fifteen canonical keys `event_id`, `date`,
  `fiscal_week`, `customer_id`, `segment`, `region`, `sku`, `category`, `kind`,
  `quantity`, `amount_usd_cents`, `currency`, `source`, `channel_group`, `warehouse`.
- `/app/out/summary.json` (new) - `record_count`, `skipped_count`, `total_usd_cents`, and
  the five breakdown maps `by_region`, `by_segment`, `by_kind`, `by_category`,
  `by_channel_group`, each
  mapping a bucket name to summed USD cents with sorted keys.
- `/app/out/data_quality.json` (new) - `input_files` (every regular file in the input
  directory, sorted by name), `records_by_source`, `skipped_count`, and the two empty
  identifier lists.
- `/app/out/product_summary.json` (new) - a `products` array covering every SKU in the
  catalogue, sorted by SKU, including SKUs that no transaction touched, each entry joining
  the transaction tallies to the summed inventory figures.
- `/app/out/region_central.json`, `region_east.json`, `region_north.json`,
  `region_south.json`, `region_west.json` (new) - one file per canonical region, always
  all five, present even when a region drew no transactions.
- `/app/out/segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json`,
  `segment_smb.json` (new) - one file per canonical segment, always all four, on the same
  always-present rule.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is mirrored by
the reference `solution/solve.py`. This section names the deliverables so a reader knows
the shape of the work, not the text to type.

Out of bounds by design: any artifact whose values depend on the shipped sample rather
than on the input directory passed in; a transform that cannot run twice into two
different output directories and produce identical bytes; emitting only the buckets that
happen to be populated; and any write outside the given output directory.

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

Channel A declares 13 positive and 4 negative tests, positive weight total
51 and negative weight total -16, so the
theoretical reward range is -16/51 = -0.314 to +1.000.

Positive tests (13):

- `artifacts_exist` (weight 3)
- `transform_script_is_executable_python` (weight 3)
- `visible_normalized_jsonl_exact` (weight 5)
- `visible_summary_exact` (weight 5)
- `data_quality_exact` (weight 3)
- `product_summary_exact` (weight 3)
- `region_outputs_exact` (weight 5)
- `segment_outputs_exact` (weight 5)
- `output_format_is_canonical_and_deterministic` (weight 3)
- `reusable_transform_regenerates_visible_outputs_elsewhere` (weight 5)
- `hidden_row_order_and_currency_transform_correctly` (weight 5)
- `transform_avoids_network_dependencies_and_shelling_out` (weight 3)
- `transform_does_not_write_outside_output_dir` (weight 3)

Negative tests (4) are polarity-inverted: their assertions hold
only when the cheat is present, so an honest run leaves them "failing" and contributes
zero weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_embedded_visible_records` (weight -5)
- `negative_network_dependency_or_shell_cheat` (weight -3)
- `negative_nondeterministic_output` (weight -3)

Channel B is 11 criteria (9 positive / 2 negative), positive total 33:

- **R1** (+3, trajectory): The agent inspects all eleven data files and the schema note before designing the transform.
- **R2** (+5, trajectory): The agent derives a general normalization strategy across CSV, JSON Lines, pipe-delimited text, and lookup tables rather than manually transcribing visible outputs.
- **R3** (+5, trajectory): The agent handles exact FX monetary conversion, signed values, joins, deterministic sort order, and fixed region/segment aggregates.
- **R4** (+3, trajectory): The agent implements the reusable transform with Python standard-library facilities and honors command-line data/output directories.
- **R5** (+5, trajectory): The agent runs the reusable transform entry point with the requested input and output locations during the working session.
- **R6** (+3, trajectory): The agent verifies the pipeline on local data and at least one nontrivial additional case before finishing.
- **R7** (+3, trajectory): The agent keeps all fourteen generated outputs deterministic and validates aggregate semantics from evidence.
- **R8** (-5, trajectory): The agent retrieves hidden cases, a prior solution, or task-specific output answers from an external source.
- **R9** (-5, trajectory): The agent hardcodes visible filenames or outputs while claiming to have built a general reusable pipeline.
- **R10** (+3, user_facing_message): The response summarizes the completed work and names where the produced artifacts were written.
- **R11** (+3, trajectory): The agent writes every requested output artifact under the specified output directory using the deterministic filenames the instruction names.

The decisive test is `hidden_row_order_and_currency_transform_correctly`: it copies
the visible corpus to a temporary directory, reshuffles the rows of `sales.csv` using
`EVAL_SEED = 6449632170523823810` - distinct from the visible `SAMPLE_SEED = 4123951422061157855` and
the labelled `CHALLENGE_SEED = 2766443677920801265` - reruns the delivered script there, and
demands the full expected payload set. Because the transform sorts by `event_id`, a
correct implementation is indifferent to the shuffle;
`reusable_transform_regenerates_visible_outputs_elsewhere` makes the same point about
location. The oracle expectation is that running `solution/solve.sh` inside the container
drives every positive Channel A test to pass and holds every negative test in its failing
state.

## Root cause

**The corpus is regenerated, so generality is the whole task.** Two of the highest-weighted
tests run the delivered `transform.py` against directories that did not exist when it was
written. Every design choice should be tested against the question "does this still hold if
the SKU list, the currency set, and the row order all change?" A lookup table built from
the visible catalogue answers no; a lookup table built by reading whatever
`product_catalog.csv` is in the input directory answers yes.

**Decimal discipline, once, at the last moment.** `Decimal(str(value))` is the entry point
 -  constructing a `Decimal` from a float carries the float's error into the exact
arithmetic and defeats the point. The chain is amount × rate × 100, quantized once with
`ROUND_HALF_UP` to a whole cent, then cast to `int`. `ROUND_HALF_EVEN` is Python's default
rounding mode and is *not* what the contract asks for; the difference shows up on exactly
the values that land on a half-cent, which the generated corpus is seeded to contain.

**Skip means skip, and skipping is counted, not itemised.** A row is skipped when its
`customer_id` is absent from `customers.csv` or its `sku` is absent from
`product_catalog.csv`, or when any field fails to parse. Skipped rows increment
`skipped_count` and appear nowhere else: not in `records_by_source`, not in the two
identifier lists, not in any bucket. Rows are *not* skipped for missing optional fields  - 
an absent note, reason, or channel is normal, and dropping those rows quietly deletes real
money from every total.

**Buckets are fixed, not discovered.** The five regions and four segments are constants
from the contract, and all nine files are written every run. Enumerating the regions
actually present in the data produces a correct-looking set of files with one missing, and
`region_outputs_exact` reads all five by name.

**Two serializations, one program.** Compact for the stream, indented for the documents.
The reason is that the JSONL is compared line-for-line against canonical dumps while the
JSON files are compared as parsed objects plus a trailing-newline check, and mixing the
two conventions fails the comparison that is stricter than the one being satisfied.

**Determinism requirements.** Sets are unordered, dicts preserve insertion order, and
`Path.iterdir` returns whatever the filesystem hands back. Every one of those has to be
funnelled through `sorted()` before it reaches an artifact - the `customers` array in each
bucket, the keys of every `by_*` map, the `products` array, and `input_files`. Nothing may
carry a timestamp, a `uuid`, or a random value.

**Red lines.** No embedded sample records or answers; no hardcoded input or output paths;
no shelling out and no third-party imports; no writes outside the output directory; no
non-deterministic ordering or content; no online lookup.

## Solution shape

1. Read the input directory path and the output directory path from `sys.argv`, falling
   back to the `INPUT_DIR` and `OUTPUT_DIR` environment variables and then to `/app/data`
   and `/app/out`. Everything downstream is expressed relative to those two values.
2. Build the reference maps from whatever is in the input directory: `customer_id` →
   segment and home postal code; postal prefix → region and default currency; `sku` →
   category; terminal → channel group; `(date, currency)` → USD rate as a `Decimal`;
   `date` → fiscal week; warehouse → postal code; and `sku` → inventory, *accumulating*
   `on_hand` and `reorder_point` across every warehouse row.
3. Yield transaction bases from the four sources in a fixed order, converting each to
   signed USD cents at the point of yield so the sign convention lives beside the parser
   that knows it. `sales.csv` multiplies quantity by unit price; `refunds.csv` negates the
   absolute refund amount; `adjustments.jsonl` divides its signed cents by 100 before
   conversion; `legacy.txt` skips blanks and `#` comments, splits on `|`, and applies the
   sign implied by the `kind` token.
4. Normalize each base into the canonical fifteen-key record by walking the lookup
   chain (region from warehouse or home postal code, blank currency from the region,
   then the dated rate), raising when any lookup fails. Catch that raise at the call
   site, increment the source's skipped tally, and continue; otherwise append the
   record and increment the per-source accepted tally.
5. Sort the accepted records by `event_id` and write `normalized.jsonl` as compact
   sorted-key JSON, one record per line with `\n` endings.
6. Fold the records into `summary.json`: three scalars plus five breakdown maps built by
   summing `amount_usd_cents` per bucket key and emitting the keys sorted.
7. Write `data_quality.json` from the sorted input-file listing, the per-source accepted
   and skipped tallies, and the skipped total; then `product_summary.json` by iterating the
   catalogue in SKU order and joining each SKU's records to its summed inventory.
8. Write the nine bucket files through one shared routine parameterised by the grouping
   key, each carrying the bucket name, record count, total cents, net units, the sorted
   contributing customers, and the sorted `by_kind` and `by_category` maps.

## Ordered plan

1. Read `schema.md` end to end, then open all twelve files and confirm the contract against
   the bytes - column orders, the comment lines in `legacy.txt`, the repeated SKU rows in
   `inventory.csv`, the dated rows in `fx_rates.csv`, the postal prefixes that link
   customers and warehouses to `regions.csv`. Rubric R1 credits exactly this:
   inspecting all eleven data files and the schema note before designing the
   transform.
2. Decide the four sign conventions and the one conversion routine before writing a parser,
   and write them down. Rubric R2 credits deriving a general normalization strategy across
   CSV, JSON Lines, pipe-delimited text, and lookup tables rather than transcribing the
   visible outputs.
3. Implement the `Decimal` conversion first and test it by hand on three rows in three
   currencies, checking that a half-cent value rounds up rather than to even. Rubric R3
   credits handling exact FX monetary conversion, signed values, joins, deterministic sort
   order, and the fixed region and segment aggregates.
4. Build the reference maps and the record normalizer, then run the transform against
   `/app/data` and read `normalized.jsonl`. Verify a sale, a refund, an adjustment, and a
   legacy row individually against arithmetic done by hand.
5. Add the aggregates one artifact at a time, checking after each that
   `sum(by_region.values())`, `sum(by_segment.values())`, `sum(by_kind.values())`, and
   `sum(by_category.values())` all equal `total_usd_cents`. Any inequality means a record
   is being double-counted or dropped.
6. Run the transform explicitly with both directories on the command line, into a
   directory that is not `/app/out`. Rubric R4 credits implementing the reusable transform
   with the standard library and honouring command-line data and output directories, and
   rubric R5 credits actually running that entry point with the requested locations during
   the session.
7. Copy the corpus to a scratch directory, shuffle the rows of `sales.csv`, add a row
   naming an unknown SKU, and rerun. The shuffled run must produce byte-identical
   artifacts; the unknown-SKU run must raise `skipped_count` by one and change nothing
   else. Rubric R6 credits verifying the pipeline on local data and at least one nontrivial
   additional case, and rubric R7 credits keeping all fourteen outputs deterministic while
   validating aggregate semantics from evidence.
8. Run twice into two clean directories and diff every artifact byte for byte, then close
   with a summary naming what was built and where each artifact was written - rubric R10
   credits exactly that closing summary.

## Pitfalls

- **Reading the visible outputs and writing them back.** The corpus is regenerated for
  grading, so this scores zero on the tests that matter and fires both
  `negative_hardcoded_sample_answers` and
  `negative_embedded_visible_records`.
- **Defaulting the paths inside the functions instead of at the entry point.** A transform
  that accepts arguments but ignores them for some artifacts fails
  `reusable_transform_regenerates_visible_outputs_elsewhere` on precisely those
  artifacts, which reads as a data bug rather than a plumbing bug.
- **Floats anywhere in the money path.** `float(row["unit_price"]) * rate` looks exact for
  small values and drifts by a cent across a bucket. The corpus is seeded to include values
  that expose it.
- **`ROUND_HALF_EVEN` by omission.** `Decimal.quantize` without an explicit rounding mode
  uses the context default, which is banker's rounding. The contract says half-up.
- **Converting adjustments twice or not at all.** `amount_cents` is in the listed currency's
  cents, not USD cents. It has to come back to currency units and go through FX like
  everything else.
- **Treating `net_units` as signed money or as raw quantity.** Fees and credits carry cents
  but contribute zero units; refunds contribute negative units. Getting this wrong fails
  the product, region, and segment comparisons simultaneously.
- **Overwriting inventory rows instead of summing them.** One SKU, several warehouses. A
  plain assignment keeps the last one seen and the number looks plausible.
- **Taking every region from the customer.** Only adjustments use the customer's home
  postal code; everything else ships from a warehouse whose postal code decides it.
- **Converting a blank currency as USD.** It is the region's `default_currency`.
- **Keying `records_by_source` on bare source names.** The contract keys it on the
  `source` field, which is the file name including its extension.
- **Sorting `normalized.jsonl` by date, or leaving it in read order.** The sort key is
  `event_id`, compared as a string, and the hidden test shuffles the input rows specifically
  to catch a pipeline that preserved file order by accident.
- **Pretty-printing the JSONL, or compacting the JSON.** The two serializations are
  different and `output_format_is_canonical_and_deterministic` checks both.
- **Omitting a bucket file because no transaction landed in it.** All five regions and all
  four segments are written every run, with zeroes and empty maps where appropriate.
- **Dropping rows for absent optional fields.** A missing note, reason, or channel is
  normal. Skipping those rows removes real money from every total and shows up as a
  `skipped_count` the grader does not expect.
- **Emitting a set, or an unsorted dict.** The `customers` array and every `by_*` map must
  be sorted before serialization, or the artifact differs run to run and
  `negative_nondeterministic_output` fires.
- **Reaching for `subprocess`, `csvkit`, or `pandas`.** The grading image has neither the
  packages nor the network, and
  `transform_avoids_network_dependencies_and_shelling_out` reads the source.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: metered-usage-rating-pipeline
task_name: terminal-bench/metered-usage-rating-pipeline
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 0f8b89e76a0f3115f48f444bd18e8fed59fd26aba8bfa7fe18dabe0679fe5bb1  # informational; solve.py is 242 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each of five
  oracle runs and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 13 positive checks worth 51 weight and 4 negative
  checks worth -16 weight, so on its own it ranges -16/51 = -0.314 to
  +1.000. The judged channel carries 11 criteria worth 33 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -1.000 to +1.000 with no clamp.
```
