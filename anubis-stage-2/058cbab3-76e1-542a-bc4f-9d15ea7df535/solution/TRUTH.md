# TRUTH.md - 058cbab3-76e1-542a-bc4f-9d15ea7df535

## Defect

Nothing is broken here, everything is absent. `/app/data` holds thirteen input
files in seven formats (csv, tsv, jsonl, txt, log, json, ini) plus the written
contract `schema.md`, about twenty-eight thousand six hundred lines in all, and
no code. The deliverable is a reusable transform plus thirteen exact artifacts
and a closing message carrying nine figures that no artifact holds. No file can
be skipped: a reading reaches its zone, currency, rate, billing cycle and route
group only through a chain that crosses every reference file, and whether the
reading posts at all depends on the state of its account's prepay wallet at the
moment it lands. The grading side reruns the delivered script against a
relocated copy, against a permuted copy with one currency's rate curve moved,
against a copy with one tariff class's readings removed, against a copy holding
only three of the four reading files, and twice over one unchanged copy, so
every figure has to fall out of the rules rather than out of
the shipped bytes and the same book has to post to the same bytes every time. Identifiers, amounts, currencies, floors and row counts are
specific to this task instance, so nothing below can be recalled from training.

0. (focal) The prepay wallet gate is a feedback loop, and it is the spine. Each
   account keeps one running balance that opens at
   `opening_credit_minor / 100` converted at the `[wallet] opening_rate_date`
   rate. Readings are then taken in order of UTC instant with `reading_id`
   breaking a shared instant. A non-negative reading posts and raises the
   balance. A negative reading posts only when the balance it would leave is at
   or above the `[disconnection]` floor for that account's tariff class, and is
   otherwise credit held: the balance does not move, the reading leaves
   `normalized.jsonl` and every money total, and it is counted against its own
   file, zone and tariff class. Acceptance of reading N therefore depends on the
   posted fold through N-1, and holding N changes the state that N+1 is judged
   against. The two-phase shape every weak solution reaches for, filter the
   breaching charges against the opening balance and then fold the survivors,
   cannot express this: it measures 0.107 against the oracle's 1.000, and
   dropping the gate altogether measures 0.226.
1. (focal) Money is one exact decimal expression. The gross amount, the USD
   rate and the factor of 100 multiply together and the product is quantized
   exactly once under the `[rounding]` mode in `policy.ini`. The corpus is
   seeded so that one thousand three hundred and fifty seven posted readings
   land on an exact half cent, which is where half up parts company with both
   float arithmetic and banker's rounding. Banker's rounding measures 0.345,
   float arithmetic 0.345, and rounding the gross to cents before applying the
   rate 0.345. The cents also have to reach the artifacts as JSON integers,
   because the artifact comparisons read types as well as values.
2. (focal) The resolution chain crosses every reference file and branches by
   source. Consumption, remittance and legacy rows take their postcode from the
   metering site in `meter_sites.csv`; levies take the account's own. Reading
   the account postcode for all four sources measures 0.048.
   `service_zones.csv` turns a postcode prefix into a zone, and the reporting
   bucket is that zone's top level ancestor, reached by walking `parent_zone`
   through up to two intermediate levels; stopping at the leaf measures 0.643. A
   blank currency, which five hundred and four rows carry once the amendments
   are applied, falls back to the matched prefix row's `default_currency`, not
   to the ancestor's and not to USD; defaulting to USD measures 0.048, and only
   then can the dated rate be found.
3. (focal) Time is local at the metering site and has to be moved to UTC before
   anything keys off it. `utc_offset_minutes` lives on every `meter_sites.csv`
   row for that site and may be negative; levies already carry `Z`. Two thousand
   seven hundred and sixty one posted readings change calendar day under the shift,
   which moves their rate lookup, their billing cycle, their day bucket and
   their position in the wallet order. Posting on the local date measures 0.107.
4. (focal) `amendments.log` rewrites raw fields before any parsing happens. The
   winner per `(target, field)` is the greatest `utc_ts`, and a shared greatest
   timestamp is broken by the later line in file order. An amendment naming a
   field its target's own file does not have is ignored. An amendment naming no
   reading at all is reported in `unmatched_amendment_targets`, and so is one
   whose target appears only on a line the contract calls malformed, since such
   a line yields no reading to match: two of the thirty three unmatched targets
   are of that kind. A replacement counts as applied even where the text it
   writes is the text already there, which twenty four readings rely on.
   Amendments cut both ways in this corpus: some turn a clean row malformed and
   some repair a malformed one, so applying them after parsing, or not at all,
   changes eight hundred and ten readings and measures 0.048.
5. (drift) Billing cycles come from the `cycles` array in
   `billing_calendar.json` as closed date spans, not from the calendar month.
   Thirteen twenty six day cycles run from 2040-10-01 with three day gaps
   between them and leave the tail of the year uncovered, so the
   `unassigned_cycle` label from `policy.ini` is a real bucket in
   `by_billing_cycle` and not an error.
6. (drift) The rate rule reaches backwards only. When a currency has no row on
   the posting date the most recent earlier row applies, and a currency with no
   row on or before that date makes the reading malformed. Fifty one rows carry
   a currency whose curve starts months after they were read. Taking the nearest
   row in either direction measures 0.226.
7. (drift) `accounts.csv` carries two thousand four hundred and forty three
   revision rows for four hundred and eighty four accounts. The surviving row is
   the one with the greatest `revised_at`, and thirty two accounts carry two
   rows sharing that greatest stamp with different tariff classes, where the
   later line in file order wins. First row dedup measures 0.107, because the
   class it picks carries the wrong disconnection floor and the wrong opening
   credit into the gate.
8. (drift) Opening credits are in the minor units of `opening_currency`, not in
   USD cents, and they are converted at the `[wallet] opening_rate_date` rate
   under the same single quantize rule. Eighty seven accounts open below their
   own floor, which is not an error, and thirty four accounts have no readings
   at all yet still contribute their closing wallet to
   `wallet_closing_usd_cents`.
9. (trap) The orphan test is judged on the raw rows of `consumption.csv`, with
   no regard for whether the charge posted, and it reads the amended
   `charge_reading_id`. Two hundred and seventy remittances link to a
   consumption row that is present but never posted, so judging the link against
   the posted set turns them into orphans; that measures 0.048. Orphan also wins
   over malformed, and sixteen orphans carry a second broken field to prove it.
10. (trap) Twenty four accounts are funded so that one charge lands the balance
    exactly on the floor, which makes "at or above" a live decision: reading it
    as "strictly above" measures 0.226. Those same accounts carry two charges on
    one shared UTC instant, each affordable alone and not together and a cent
    apart, laid into `consumption.csv` with the later id first, so a stable sort
    on the instant alone holds the wrong one of the two and moves every money
    total: that measures 0.226. Testing the floor against the balance before the
    reading rather than the balance it would leave measures 0.107.
11. (trap) A levy carries its own sign in `amount_minor`, and the sign that
    reaches the wallet is that column's and never one implied by `kind`. The
    neighbouring `legacy_reads.txt` rule is the opposite, taking `-abs(amount)`
    for `surcharge` and `+abs(amount)` for `rebate`, so carrying the legacy rule
    across to the levies is the natural mistake. Sixty levies are seeded against
    the grain to price it: thirty surcharges carry a positive `amount_minor` and
    thirty rebates a negative one, spread over fifty eight accounts, so the two
    readings part company on the wallet fold and on every roll-up the affected
    accounts touch. Taking the levy sign from `kind` measures 0.107. The reverse
    confusion is already priced: every `legacy_reads.txt` amount is unsigned, so
    taking the legacy sign from its column instead of its kind turns 1121
    consumption and surcharge rows positive.

## Load-bearing work

Fourteen artifacts are collected, and every one of them is graded:

- `/app/out/transform.py` (new) is the deliverable itself, an executable
  stdlib-only script runnable as `python3 /app/out/transform.py DATA_DIR OUT_DIR`.
  It is read as source by the anti-cheat checks and re-executed against a
  relocated corpus, a permuted corpus, a corpus with one tariff class stripped
  out and the same corpus twice by the correctness checks, so it is both the
  program and a graded artifact. It creates the output directory it is handed
  when that directory is missing.
- `/app/out/normalized.jsonl` (new) is one compact JSON object per posted
  reading, ordered by `reading_id` as text, carrying the sixteen canonical keys
  `reading_id`, `posting_date`, `utc_instant`, `billing_cycle`, `account_id`,
  `tariff_class`, `zone`, `tariff_code`, `category`, `kind`, `units`,
  `posted_usd_cents`, `currency`, `source`, `route_group`, `meter_site`.
- `/app/out/summary.json` (new) carries `event_count`, `skipped_count`,
  `held_count`, `orphan_remittance_count`, `total_usd_cents`, `net_units`,
  `wallet_closing_usd_cents` and the seven breakdown maps `by_zone`,
  `by_tariff_class`, `by_kind`, `by_category`, `by_route_group`,
  `by_billing_cycle` and `by_source`.
- `/app/out/data_quality.json` (new) carries `input_files`,
  `records_by_source`, `skipped_by_source`, `held_by_source`, the three counts,
  and the three sorted duplicate-free id lists `held_reading_ids`,
  `orphan_remittance_ids` and `unmatched_amendment_targets`.
- `/app/out/product_summary.json` (new) is a `tariffs` array covering every one
  of the 2050 catalogue codes in order, including the codes no reading touched,
  joining the posted tallies to the summed metering capacity.
- `/app/out/region_central.json`, `region_east.json`, `region_north.json`,
  `region_south.json`, `region_west.json` (new) are one file per top level zone,
  always all five, present even when a zone drew nothing.
- `/app/out/segment_consumer.json`, `segment_corporate.json`,
  `segment_enterprise.json`, `segment_smb.json` (new) are one file per tariff
  class, always all four, each carrying its own
  `disconnection_floor_usd_cents`.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is
mirrored by the reference `solution/solve.py`. This section names the
deliverables so a reader knows the shape of the work, not the text to type.

Out of bounds by design: any artifact whose values depend on the shipped bytes
rather than on the input directory passed in; a transform that cannot run twice
into two different output directories and produce identical bytes; emitting only
the buckets that happen to be populated; and any write outside the given output
directory.

## Verification

Entrypoint: `tests/test.sh`. It clears stale reward files, locks
`/logs/verifier` to root, restricts `/tests`, and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores the test channel from the `@criterion` checks in
`tests/test_output.py`, each weighted by its `criteria.<name>(weight=W)`
registration, and the judged channel from the criteria in `tests/judge.toml`,
read against `/logs/agent/trajectory.json`. `tests/reward.toml` divides each
channel's weighted sum by that channel's positive total and gives each half of
`reward`.

The test channel declares 25 checks: 22 positive worth 84 weight and 3 negative
worth -11 weight, so on its own it ranges -11/84 = -0.131 to +1.000. Four
checks need nothing but the right shapes, so a solver that lands only those is
capped at 4/84 = 0.048.

Positive checks (22):

- `artifacts_exist` (1)
- `output_serialization_is_canonical` (1)
- `data_quality_lists_every_input_file` (1)
- `product_summary_lists_every_tariff_code` (1)
- `wallet_gate_holds_exactly_the_right_readings` (5)
- `normalized_stream_is_exact` (5)
- `summary_totals_are_exact` (5)
- `zone_rollups_are_exact` (5)
- `class_rollups_are_exact` (5)
- `tariff_summary_is_exact` (5)
- `data_quality_ledger_is_exact` (5)
- `fx_carry_back_and_predated_currency_are_exact` (5)
- `utc_day_shift_and_billing_cycle_are_exact` (5)
- `account_dedup_class_is_exact` (5)
- `half_cent_money_rounds_half_up` (5)
- `orphan_links_use_raw_consumption_ids` (5)
- `amendments_log_overrides_are_applied` (5)
- `reusable_transform_posts_a_relocated_book` (5)
- `permuted_rows_and_shifted_rates_post_identically` (5)
- `empty_bucket_files_are_still_written` (1)
- `book_missing_one_reading_file_posts_exactly` (1)
- `policy_constants_are_read_from_the_file` (3)

Negative checks (3) are polarity-inverted: their assertions hold only when the
cheat is present, so an honest run leaves them failing and contributes zero
weight. They subtract only from a solver that actually cheats.

- `negative_hardcoded_sample_answers` (-5) holds when the shipped book's own
  posted totals, or ten or more of its account and tariff ids, sit inside
  `transform.py`.
- `negative_network_dependency_or_shell_cheat` (-3) holds when the parsed syntax
  tree of `transform.py` imports a package outside the standard library, reaches
  the network, or spawns a process.
- `negative_nondeterministic_output` (-3) holds when two runs over one unchanged
  book disagree on the bytes of any artifact.

The judged channel carries 21 criteria worth 61 positive points, 4 of them
negative and worth -16 together.

The decisive check is `permuted_rows_and_shifted_rates_post_identically`: it
copies the book to a temporary directory, shuffles the rows of every file whose
order the contract leaves free, multiplies one whole currency curve by 1.0425,
reruns the delivered script there, and demands the full payload set re-derived
from those bytes. `reusable_transform_posts_a_relocated_book` makes the same
point about location. The oracle expectation is that `solution/solve.sh` inside
the container drives all 22 positive checks to pass and holds all 3 negative
checks in their failing state, for exactly 1.000 on the test channel.

## Root cause

**The gate is a fold, not a filter.** The only shape that reproduces
`held_reading_ids` is one chronological pass per account that carries the
balance forward and decides each reading against the balance the previous
decisions left standing. Any shape that decides acceptance before folding, or
that folds before deciding, gets a different held set, a different
`wallet_closing_usd_cents`, and different totals in every roll-up the held
readings touch.

**Decimal discipline, once, at the last moment.** `Decimal(str(value))` is the
entry point; constructing a `Decimal` from a float carries the float's error
into the exact arithmetic. The chain is gross times rate times 100, quantized
once under the `[rounding]` mode, then cast to `int`. `ROUND_HALF_EVEN` is
Python's context default and is not what `policy.ini` asks for; the difference
shows up on exactly the values that land on a half cent, which this corpus is
seeded to contain in volume.

**Skip means skip, and skipping is counted, not itemised.** A reading is
malformed when any field it needs fails to parse or any lookup in the chain
misses. It increments `skipped_by_source` and appears nowhere else. Readings are
not skipped for an absent `note`, `memo`, `firmware` or `inspector`.

**Orphan precedence sits above malformed.** The link test reads the amended
`charge_reading_id` and runs before any other field of the remittance is parsed,
so a remittance it names is an orphan even when another of its fields would have
failed, and it is counted in no file's skipped tally.

**Buckets are fixed, not discovered.** The five zones and four tariff classes
are constants from the contract, and all nine files are written every run.
`empty_bucket_files_are_still_written` strips one class out of a scratch copy
and demands its segment file anyway, so emitting only the populated buckets
costs that check.

**Two serializations, one program.** Compact for the stream, two space indent
for the documents, because the stream is compared line for line against
canonical dumps while the documents are compared as parsed objects plus a
trailing newline check.

**Determinism requirements.** Sets are unordered and `Path.iterdir` returns
whatever the filesystem hands back. Every one of those has to pass through
`sorted()` before it reaches an artifact, or the bytes differ run to run and
`negative_nondeterministic_output` fires.

## Solution shape

`solution/solve.py` writes `/app/out/transform.py` and runs it once over the
shipped book. The transform, in order:

1. reads `policy.ini` for the four class floors, the wallet opening rate date,
   the rounding mode, `litres_per_kilolitre` and the two labels;
2. builds every reference table through one loader function per file and keeps
   them in a flat `Refs` NamedTuple: the surviving account row per id, the
   prefix to zone and default currency maps, the whole `parent_zone` hierarchy
   folded once into a path-compressed top level ancestor map, the tariff
   catalogue, the collector route groups, the metering site postcodes, offsets
   and summed capacity, two parallel sorted lists per currency for the rate
   curve, and the billing cycles as parallel opens/closes/name lists;
3. indexes `amendments.log` as a nested `target` to `field` mapping, keeping the
   greatest `utc_ts` and breaking a shared greatest on file order;
4. streams the four reading files, patches each row with the amendments naming a
   column of its own file, applies the orphan link test to remittances, and
   projects what survives into a `Posting` NamedTuple whose own fields carry the
   three report flags;
5. settles each account's wallet in one chronological pass, splitting the
   survivors into posted and credit held and accumulating every account's
   closing balance;
6. emits the fourteen artifacts with sorted keys and integer cents, creating the
   output directory when it is missing, and prints the nine closing figures.

It is standard library only, takes `<DATA_DIR> <OUT_DIR>`, falls back to
`/app/data` and `/app/out`, and is byte stable across runs.

The transform is deliberately not built like the verifier's own expectation
engine. That engine keeps its reference tables in one `_Vault` object, resolves
a rate by hitting an exact `(date, currency)` dict and falling back to
`bisect_left`, walks the `parent_zone` chain per record, keys amendments on flat
`(target, field)` tuples, carries each record as a plain dict with its flags in a
side table keyed by `id()`, and scans the cycle list linearly. This transform
uses loader functions and a NamedTuple, `bisect_right` over parallel sorted
columns with no exact-hit shortcut, a precomputed ancestor map, a nested
amendment index, flags as NamedTuple fields, a bisected cycle lookup, and a
per-feed dispatch table for the four money rules. The two sides agree on output
byte for byte while sharing only the handful of one-line primitives the contract
dictates verbatim, so the oracle run is evidence that two independent readings
of `schema.md` reach the same book rather than evidence that one file agrees
with itself.

## Ordered plan

1. Read `schema.md` end to end, then open all thirteen inputs and confirm the
   contract against the bytes: the comment and blank lines in
   `legacy_reads.txt`, the repeated tariff code rows in `meter_sites.csv`, the
   holes in `currency_rates.csv`, the revision rows in `accounts.csv`, the
   prefixes that link sites and accounts to `service_zones.csv`. Rubric R13
   credits exactly this.
2. Read `policy.ini` and take the six constants from it at run time rather than
   writing them into the program. Rubric R11 credits taking them from the file,
   and `policy_constants_are_read_from_the_file` reposts the book from a copy
   whose floor, rounding mode, volume factor and both labels have been moved.
3. Implement the single decimal conversion first and check by hand that a
   product landing on the half cent rounds away from zero rather than to even.
   Rubric R12 credits one exact expression quantized a single time.
4. Build the reference maps and the record projector, then post `/app/data` and
   read `normalized.jsonl`. Verify one consumption, one remittance, one levy
   and one legacy row against arithmetic done by hand, including the UTC shift.
5. Implement the wallet fold as one pass per account and reconcile
   `sum(by_zone.values())`, `sum(by_tariff_class.values())`,
   `sum(by_kind.values())` and `sum(by_source.values())` against
   `total_usd_cents`. Rubric R10 credits the interleaved fold.
6. Run the transform explicitly with both directories on the command line, into
   a directory that is not `/app/out`. Rubric R14 credits that run.
7. Copy the book to a scratch directory, shuffle the rows of the files whose
   order the contract leaves free, and rerun. The artifacts must be byte
   identical. Rubric R15 credits that reordered second corpus.
8. Run twice into two clean directories and diff every artifact byte for byte,
   then close with a message naming what was built, where each artifact went,
   and the nine closing figures. Rubric R16 credits naming the destinations and
   R1 through R9 credit the figures. Rubric R21 credits a transform a reviewer
   of ordinary Python practice would accept: named helpers, handled errors and
   no debug residue.

## Pitfalls

- **Filtering the breaching charges and then folding the survivors.** The
  natural two-phase shape scores 0.107: acceptance of each reading depends on
  the balance the earlier decisions left, not on the opening balance.
- **Dropping the gate.** Posting everything scores 0.226.
- **`ROUND_HALF_EVEN` by omission.** `Decimal.quantize` without an explicit
  rounding mode uses the context default, which is banker's rounding. The policy
  file says half up, and 1357 readings sit exactly on the boundary.
- **Floats anywhere in the money path.** `float(rate_per_unit) * usd_rate` looks
  exact for small values and drifts by a cent; measured at 0.345.
- **Quantizing the gross before applying the rate.** Two roundings instead of
  one; measured at 0.345.
- **Reading `opening_credit_minor` as USD cents.** It is in the minor units of
  `opening_currency` and has to be converted at the wallet opening rate date,
  which also lands the gate on the wrong side of the floor.
- **First row account dedup.** The surviving row is the greatest `revised_at`,
  with the later line in file order breaking a shared greatest; 32 accounts flip
  tariff class on that tie, which flips their floor too. Measured at 0.107.
- **Nearest rate row in either direction.** The rule reaches backwards only, and
  a currency with no earlier row makes the reading malformed. Measured at 0.226.
- **Posting on the local date.** 2761 readings change calendar day under the
  offset, which also moves their rate and their cycle. Measured at 0.107.
- **Taking every postcode from the account.** Only levies use the account's own;
  everything else ships from a metering site. Measured at 0.048.
- **Stopping at the leaf zone instead of the top level ancestor.** Measured at
  0.643.
- **Defaulting a blank currency to USD.** It is the matched prefix row's
  `default_currency`. Measured at 0.048.
- **Skipping `amendments.log`, or applying it after parsing.** It rewrites raw
  fields before any parsing, and it both breaks clean rows and repairs broken
  ones. Measured at 0.048.
- **Judging the orphan link against the posted set.** Presence is judged on the
  raw rows of `consumption.csv`. Measured at 0.048.
- **Reading the floor as strictly above, or testing it against the balance
  before the reading.** Both are live decisions in this corpus, measured at
  0.226 and 0.107.
- **Ordering a shared UTC instant by anything but `reading_id` as text.**
  Measured at 0.226.
- **Omitting a bucket file because nothing landed in it.** All five zones and
  all four classes are written every run, and the stripped-class corpus prices
  it at 1 of 84.
- **Hardcoding the six `policy.ini` constants.** The floors, the rounding mode,
  `litres_per_kilolitre` and the two labels have to be read from the file on
  every run, because the policy-sourcing check reposts the book from a copy
  whose values have been moved. Carrying the shipped values in the source
  measures 0.964.
- **Hardcoding the four reading file names, or the input file list.** The
  contract keys `skipped_by_source` and `held_by_source` on the reading files
  the directory actually holds, and `input_files` on every regular file it
  holds, so both have to be read off the directory. The three-feed corpus
  prices it at 1 of 84.
- **Emitting a set, or an unsorted dict.** Every `by_*` map, every id list and
  the `accounts` array must be sorted, or `negative_nondeterministic_output`
  fires.
- **Taking the levy sign from `kind`.** `legacy_reads.txt` fixes the sign from
  the kind token, but `levies.jsonl` does not: `amount_minor` carries its own
  sign and sixty levies run against the grain, so carrying the legacy rule
  across measures 0.107.
- **Reaching for `subprocess`, `requests` or `pandas`.** The image has neither
  the packages nor the network, and
  `negative_network_dependency_or_shell_cheat` reads the parsed source.
- **Writing the shipped answers into the program.**
  `negative_hardcoded_sample_answers` reads `transform.py` for the book's own
  totals and for its account and tariff ids.

## Provenance

```yaml
uuid: 058cbab3-76e1-542a-bc4f-9d15ea7df535
instance_id: 058cbab3-76e1-542a-bc4f-9d15ea7df535
task_name: terminal-bench/058cbab3-76e1-542a-bc4f-9d15ea7df535
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 441613b10184bd86c841b1bede278e4cc8c88d4dfd40d1218b86dbf7cc9e6504  # informational; solve.py is 800 lines
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_verified_by: >
  Measured: the oracle transform scores every positive test-channel check and
  leaves all three negative checks unfired, for 84/84 positive weight and
  exactly 1.000 on the test channel; the judged channel has no oracle score. A
  naive solver taking every obvious shortcut at once (no gate, nearest-date
  rate, float rounding, first-row dedup, orphans against the posted set,
  amendments ignored) scores 0.048, which is the four weight-1 shape checks and
  nothing else. Eighteen single-rule references were then measured on the same
  channel, each one the reference transform deviated in exactly that one rule
  and scored over the shipped book: two-phase gate 0.107, no gate 0.226,
  banker's rounding 0.345, float money 0.345, gross quantized before the rate
  0.345, first-row dedup 0.107, nearest-date rate 0.226, amendments skipped
  0.048, orphans against the posted set 0.048, local date 0.107,
  account postcode everywhere 0.048, leaf zone 0.643, USD default currency
  0.048, shared instant ordered by instant alone 0.226, floor read as strictly
  above 0.226, floor tested against the pre-reading balance 0.107, the levy
  sign taken from `kind` 0.107, and the six policy constants hardcoded instead
  of read from `policy.ini` 0.964. An empty run scores 0.000 and a shape-only
  forgery, one empty file per declared artifact, scores 0.012 (1 of 84).
closing_report: >
  held_value_usd_cents -937868578, held_accounts 222,
  carry_back_rate_events 1445, day_shift_events 2761, amended_readings 810,
  half_cent_events 1357, underfunded_accounts 87,
  uncatalogued_capacity_litres 2463921, stale_link_remittances 100.
corpus_shape: >
  8635 posted readings, 626 credit held, 433 skipped as malformed, 174 orphan
  remittances, 484 accounts across four tariff classes and five top level zones,
  2050 catalogue tariff codes of which 1007 are touched, 13 billing cycles plus
  the unassigned bucket.
caveat: >
  The test channel carries 22 positive checks worth 84 weight and 3 negative
  checks worth -11 weight, so on its own it ranges -11/84 = -0.131 to +1.000.
  Four checks need nothing but the right shapes, so a solver that lands only
  those is capped at 4/84 = 0.048. The judged channel carries 21 criteria
  worth 61 positive points, 4 of them negative and worth -16 together, so on its
  own it ranges -16/61 = -0.262 to +1.000. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward for this bundle runs from -0.197 to +1.000 with
  no clamp.
```
