# TRUTH.md - e08c051f-cce9-5aba-b20d-88fb75574b6c

## Defect

Nothing is broken here, everything is absent. `/app/data` holds thirteen input
files in seven formats (csv, tsv, jsonl, txt, log, json, ini) plus the written
contract `schema.md`, about thirty-one thousand six hundred lines in all, and no
code. The deliverable is a reusable transform plus thirteen exact artifacts and
a closing message carrying nine figures that no artifact holds. No file can be
skipped: an event reaches its region, currency, rate, fiscal period and channel
only through a chain that crosses every reference file, and whether the event is
accepted at all depends on the state of its counterparty's ladder at the moment
it lands. The grading side reruns the delivered script against a relocated copy,
against a permuted copy with one currency's rate curve moved, and twice over one
unchanged copy, so every figure has to fall out of the rules rather than out of
the shipped bytes and the same book has to settle to the same bytes every time.
Identifiers, amounts, currencies, floors and row counts are specific to this
instance, so nothing below can be recalled from training.

0. (focal) The collateral gate is a feedback loop, and it is the spine. Each
   counterparty keeps one running balance that opens at
   `opening_balance_minor / 100` converted at the `[ladder] opening_rate_date`
   rate. Events are then taken in order of UTC instant with `event_id` breaking
   a shared instant. A non-negative event is accepted and raises the balance. A
   negative event is accepted only when the balance it would leave is at or
   above the `[collateral]` floor for that counterparty's segment, and is
   otherwise collateral blocked: the balance does not move, the event leaves
   `normalized.jsonl` and every money total, and it is counted against its own
   file, region and segment. Acceptance of event N therefore depends on the
   accepted fold through N-1, and blocking N changes the state that N+1 is
   judged against. The two-phase shape every weak solution reaches for, filter
   the breaching debits and then fold the survivors, cannot express this: the
   reference measured it at 0.241 against the oracle's 1.000. One counterparty
   carries two events on a single UTC instant, so `event_id` compared as text
   has to break the tie; taking them the other way round moves the blocked set
   and the closing ladder total.
1. (focal) Money is one exact decimal expression. The gross amount, the USD
   rate and the factor of 100 multiply together and the product is quantized
   exactly once under the `[rounding]` mode in `policy.ini`. The corpus is
   seeded so that six hundred and eighty accepted events land on an exact
   half cent, which is where half-up parts company with both float arithmetic
   and banker's rounding. Banker's rounding scores 0.304 and float arithmetic
   0.367. The cents also have to reach the artifacts as JSON integers, because
   the artifact comparisons read types as well as values.
2. (focal) The resolution chain crosses every reference file and branches by
   source. Sales, refunds and legacy rows take their postal code from the
   shipping warehouse in `inventory.csv`; adjustments take the counterparty's
   own. `regions.csv` turns a postal prefix into a region, and the reporting
   bucket is that region's top level ancestor, reached by walking
   `parent_region`. A blank currency falls back to the matched prefix row's
   `default_currency`, not to the ancestor's and not to USD, and only then can
   the dated rate be found.
3. (focal) Time is local at the warehouse and has to be moved to UTC before
   anything keys off it. `tz_offset_minutes` lives on every `inventory.csv` row
   for that warehouse and may be negative; adjustments already carry `Z`. Two
   thousand one hundred and nine accepted events change calendar day under the
   shift, which moves their rate lookup, their fiscal period, their day bucket
   and their position in the ladder order. Settling on the local date scores
   0.114.
4. (focal) `corrections.log` rewrites raw fields before any parsing happens.
   The winner per `(target, field)` is the greatest `utc_ts`, and a shared
   greatest timestamp is broken by the later line in file order. A correction
   naming a field its target's own file does not have is ignored, and a
   correction naming no event at all is reported in
   `unmatched_correction_targets`. Corrections cut both ways in this corpus:
   some turn a clean row malformed and some repair a malformed one, so applying
   them after parsing changes seven hundred and ten events.
5. (drift) Fiscal periods come from the `periods` array in
   `fiscal_calendar.json` as closed date spans, not from the calendar month.
   Thirteen twenty-eight day periods run 2027-07-01 to 2028-06-28 and leave the
   one day of the book before them and the three after them uncovered, so
   seventy-nine accepted events take the `unassigned_period` label rather than
   counting as an error.
6. (drift) `source`, `records_by_source`, `skipped_by_source` and
   `blocked_by_source` key on the input file name with its extension, and stock
   is in grams while the catalogue states mass in kilograms. Writing bare stems
   or multiplying grams by kilograms is the natural slip.
7. (trap) Orphan links are judged on the raw rows of `sales.csv`. A refund
   whose `sale_event_id` names a sales row that was itself skipped as malformed
   is still an ordinary accepted refund, because the id is present in the file;
   one hundred and five of them sit in this corpus waiting for a solver that
   checked against accepted sales instead. A `sale_event_id` that is whitespace
   only trims to empty and is not a link at all. The orphan test runs before any
   other field of the refund is parsed and `schema.md` says so, because one
   refund in this corpus is both an orphan and malformed: `EV-10028804` carries a
   dead link and a correction that moves its sku outside the catalogue, so
   without that stated precedence the one event would sit in whichever bucket the
   solver guessed, and the guess would be worth twenty-five of the seventy-nine
   positive points.
8. (trap) `counterparties.csv` repeats ids. The greatest `updated_at` wins and
   a shared greatest `updated_at` is broken by the later row in file order.
   Forty-eight ties are seeded, each with a different segment on the losing
   row, so a wrong tie-break moves the counterparty between segment buckets and
   changes the collateral floor its whole ladder is judged against.
9. (trap) `quantity` is ASCII digits and nothing else. A signed value, a
   decimal point, a word, and a digit from another script are all malformed,
   and `quantity` of `0` is valid and contributes full money with zero units.
   `legacy.txt` is latin-1 with accented bytes in its memos, so a strict utf-8
   read of it raises before any of this matters.
10. (trap) Rates have gaps. Three hundred and ninety-five accepted events have
    no row for their currency on their settlement date and must take the most
    recent earlier row for that same currency; fifty-one events name a currency
    whose first quote is later than their settlement date and are malformed.
    Nearest-date matching and USD-at-one both produce confidently wrong cents.
11. (trap) One region bucket is dormant. The west subtree is documented in
    `regions.csv` and reachable through `parent_region`, but no warehouse and no
    counterparty sits on it, so `region_west.json` has to be written with zeros
    and empty maps. Enumerating the regions present in the data produces four
    correct files and one missing one.
12. (trap) `inventory.csv` carries one row per stocking pair, so stock figures
    are sums across warehouses, and thirty-eight rows name a sku the catalogue
    does not list, which belong in the closing report and in no artifact.
13. (trap) Three rules fire exactly once each in this corpus, so a solver that
    reads the contract loosely loses them without ever seeing a pattern to warn
    it. `corrections.log` carries one correction whose `field` is `event_id`:
    that column identifies the event and is never replaced, so a solver that
    treats every `field=` token as writable renames an accepted event and breaks
    `normalized.jsonl`. One row in `refunds.tsv` carries a negative
    `refund_amount`, and the gross is minus the absolute value whatever sign the
    column holds, so a plain negation turns that debit into a credit and sends it
    through the gate the wrong way. One line in `adjustments.jsonl` carries the
    kind `writeoff`, which is neither `fee` nor `credit` and is therefore
    malformed, so a solver that validates only the legacy kind token accepts it
    and reports one accepted event too many.

The reference is authored in Python (Python 3.12, standard library only, a
589-line driver that writes and then executes the transform) with a
Bash oracle dispatcher (`solve.sh`) that runs it against `/app/data` and
`/app/out`. A deterministic channel observes the fourteen artifacts and reruns
the delivered script against relocated and permuted corpora (Channel A,
`tests/test_output.py`, weighted by its `criteria.<name>(weight=W)`
registrations); a judged rubric channel grades the nine closing figures, the
derivation trajectory and the quality of the delivered code (Channel B,
`tests/judge.toml`).

Out of bounds: memorizing the shipped book inside `transform.py`, whether as its
counterparties and skus as literals or as its own settled totals, which is one
decision and carries one penalty (`negative_memorized_shipped_book`); hardcoding
`/app/data` or `/app/out` so the script cannot be pointed elsewhere
(`reusable_transform_settles_a_relocated_book`); shelling out to `awk`, `sed`,
`sort` or a subprocess to do the work, reaching the network, or importing
anything off PyPI, all three of which the instruction rules out in so many words
(`negative_network_dependency_or_shell_cheat`); writing anywhere outside the
output directory the script was given, which breaks every rerun check; letting a
timestamp, a `uuid`, an unordered set or a dict iteration order into an artifact,
which shows up as two runs over one book disagreeing on the bytes
(`negative_nondeterministic_output`); and stating a closing figure that
contradicts the run the agent actually performed (Channel B R18).

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

- `/app/out/transform.py` (new) - the deliverable itself, a stdlib-only script
  runnable as `python3 /app/out/transform.py DATA_DIR OUT_DIR`. Its source is
  read for the dependency and shell-out anti-cheat, and it is re-executed
  against fresh corpora by the two reuse checks and twice over one unchanged
  copy by the determinism anti-cheat, so it is both the program and a graded
  artifact.
- `/app/out/normalized.jsonl` (new) - one compact JSON object per accepted
  event, sorted by `event_id` as text, carrying the sixteen canonical keys
  `event_id`, `settlement_date`, `utc_instant`, `fiscal_period`,
  `counterparty_id`, `segment`, `region`, `sku`, `category`, `kind`, `quantity`,
  `settled_usd_cents`, `currency`, `source`, `channel_group`, `warehouse`.
  Skipped, orphaned and collateral blocked events are absent from it.
- `/app/out/summary.json` (new) - `event_count`, `skipped_count`,
  `blocked_count`, `orphan_refund_count`, `total_usd_cents`, `net_units`,
  `ladder_closing_usd_cents`, and the seven breakdown maps `by_region`,
  `by_segment`, `by_kind`, `by_category`, `by_channel_group`,
  `by_fiscal_period` and `by_source`.
- `/app/out/data_quality.json` (new) - `input_files`, `records_by_source`,
  `skipped_by_source`, `blocked_by_source`, the three counts, and the three
  sorted id lists `blocked_event_ids`, `orphan_refund_event_ids` and
  `unmatched_correction_targets`.
- `/app/out/product_summary.json` (new) - a `products` array covering every
  catalogue sku, sorted by sku, including skus no event touched, each joining
  the event tallies to the summed stock grams and to `net_mass_grams`.
- `/app/out/region_central.json`, `region_east.json`, `region_north.json`,
  `region_south.json`, `region_west.json` (new) - one file per top level region,
  always all five, present even when a region drew nothing, each carrying its
  own `blocked_count`.
- `/app/out/segment_consumer.json`, `segment_corporate.json`,
  `segment_enterprise.json`, `segment_smb.json` (new) - one file per segment,
  always all four, each carrying `collateral_floor_usd_cents` from `policy.ini`.

The closing message is the fifteenth deliverable and lives only in the
transcript: nine derived figures that appear in no artifact, graded by Channel B
criteria R1 through R9.

Every rule those artifacts must satisfy lives in `tests/test_output.py` and is
mirrored by the reference `solution/solve.py`. This section names the
deliverables so a reader knows the shape of the work, not the text to type.

Out of bounds by design: any artifact whose values depend on the shipped bytes
rather than on the input directory passed in; a transform that cannot run twice
into two different output directories and produce identical bytes; emitting only
the buckets that happen to be populated; and any write outside the given output
directory.

## Verification

Grader entrypoint: `tests/test.sh`. It hardens the verifier (clears stale reward
files, locks `/logs/verifier` to root, restricts `/tests`) and then runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
rewardkit scores Channel A from the `@criterion` checks in
`tests/test_output.py`, each weighted by its `criteria.<name>(weight=W)`
registration, and Channel B from the criteria in `tests/judge.toml`, which the
judge reads against `/logs/agent/trajectory.json`. `tests/reward.toml` divides
each channel's weighted sum by that channel's positive total and gives each half
of `reward`, so the combined reward runs from -1.000 to +1.000.
The oracle and nop calibration runs score Channel A alone, on a tests-only copy
of the shipped bytes with the judged channel removed; Channel B has no oracle
score, because neither agent produces a trajectory for a judge to read.

Channel A declares 19 positive and 3 negative checks, positive weight total
79 and negative weight total -11, so the theoretical reward range is
-11/79 = -0.139 to +1.000. Four positives sit at weight 1 (total 4) and fifteen
at weight 5 (total 75), so a solver that lands only the mechanical shape checks
is capped at 4/79 = 0.051. Each negative names one decision, and no decision
fires more than one of them, so the worst a single mistake costs is 5.

Positive checks (19):

- `artifacts_exist` (weight 1)
- `output_serialization_is_canonical` (weight 1)
- `data_quality_lists_every_input_file` (weight 1)
- `product_summary_lists_every_catalogue_sku` (weight 1)
- `collateral_gate_blocks_exactly_the_right_events` (weight 5)
- `normalized_stream_is_exact` (weight 5)
- `summary_totals_are_exact` (weight 5)
- `region_rollups_are_exact` (weight 5)
- `segment_rollups_are_exact` (weight 5)
- `product_summary_is_exact` (weight 5)
- `data_quality_ledger_is_exact` (weight 5)
- `fx_carry_forward_and_predated_currency_are_exact` (weight 5)
- `utc_day_shift_and_fiscal_period_are_exact` (weight 5)
- `counterparty_dedup_segment_is_exact` (weight 5)
- `half_cent_money_rounds_half_up` (weight 5)
- `orphan_links_use_raw_sales_ids` (weight 5)
- `corrections_log_overrides_are_applied` (weight 5)
- `reusable_transform_settles_a_relocated_book` (weight 5)
- `permuted_rows_and_shifted_rates_settle_identically` (weight 5)

Negative checks (3) are polarity-inverted: their assertions hold only when the
cheat is present, so an honest run leaves them "failing" and contributes zero
weight. They subtract only from a solver that actually cheats.

- `negative_memorized_shipped_book` (weight -5), covering both memorization
  payloads, the shipped totals and the shipped ids, under one penalty
- `negative_network_dependency_or_shell_cheat` (weight -3)
- `negative_nondeterministic_output` (weight -3)

Channel B is 19 criteria (17 positive / 2 negative), positive total 57:

- **R1** (+5, user_facing_message): The response states that the collateral blocked events sum to -13292764300 settled USD cents.
- **R2** (+3, user_facing_message): The response states that 164 distinct counterparties had at least one collateral blocked event.
- **R3** (+3, user_facing_message): The response states that 395 accepted events took a rate from an earlier date.
- **R4** (+3, user_facing_message): The response states that 2109 accepted events have a settlement date that differs from the date written in their own trade_ts.
- **R5** (+3, user_facing_message): The response states that 710 distinct event ids had at least one correction applied.
- **R6** (+5, user_facing_message): The response states that 680 accepted events had a money product that landed exactly on the half cent.
- **R7** (+3, user_facing_message): The response states that 16 counterparties open below their own segment collateral floor.
- **R8** (+3, user_facing_message): The response states that the inventory rows whose sku is absent from the product catalogue sum to 685349 on hand grams.
- **R9** (+3, user_facing_message): The response states that 105 accepted refunds carry a sale_event_id that names a sales row that was skipped as malformed.
- **R10** (+3, trajectory): The agent settles each counterparty in one pass that carries the running balance forward while it decides acceptance of each event in turn.
- **R11** (+3, trajectory): The agent reads policy.ini and takes its contract constants from that file.
- **R12** (+3, trajectory): The agent builds each money figure as one exact decimal expression and quantizes it a single time at the final step.
- **R13** (+3, trajectory): The agent inspects every input file in the directory and the written contract before it designs the pipeline.
- **R14** (+5, trajectory): The agent runs the transform entry point with an explicit input directory and output directory during the session.
- **R15** (+3, trajectory): The agent verifies the pipeline against a second copy of the book whose rows have been reordered before finishing.
- **R16** (+3, user_facing_message): The response names where each produced artifact was written.
- **R17** (-3, trajectory): The agent runs one command that returns the same error on three or more consecutive turns.
- **R18** (-5, trajectory): The agent states a closing report figure that differs from the value its own pipeline produced during the session.
- **R19** (+3, trajectory): The agent writes the transform with named helper functions and specific exception types that a Python reviewer would accept.

The decisive checks are `collateral_gate_blocks_exactly_the_right_events`, which
reads the blocked id list and confirms no blocked event reached
`normalized.jsonl`, and `permuted_rows_and_shifted_rates_settle_identically`,
which copies the book to a temporary directory, shuffles the rows of the nine
files whose order the contract leaves free, multiplies one non-USD currency's
whole rate curve by 1.0375 using `EVAL_SEED = 4261055306036364168`, reruns the
delivered script there and demands the full expected payload set, then asserts
the permuted total differs from the shipped one so a memoized answer cannot
pass. `counterparties.csv` and `corrections.log` are deliberately left
unshuffled, because those are the two files whose documented tie-breaks name
file order. Each artifact carries one whole-artifact equality check, and seven
further checks read rule-scoped slices of `normalized.jsonl` and
`data_quality.json` so that a solver who gets one rule right keeps that rule's
weight even when another value is wrong. The resulting curve was measured, and
it is steeper in the middle than the per-artifact split alone suggests, because
every roll-up is derived from the record stream. An error that stays inside one
artifact costs about that artifact: one wrong `net_mass_grams` among 2060
products scores 74/79 = 0.937, one wrong `data_quality.json` count 0.937, one
missing `input_files` entry 73/79 = 0.924, and one missing blocked id 69/79 =
0.873. A serialization slip costs only the serialization check, 78/79 = 0.987,
whether it is a four space indent, a space after a separator in the stream, or a
missing final newline. An error inside the record stream cascades: one wrong cent
on one of the 10958 accepted records, carried consistently into every artifact it
touches, fails the five artifact equality checks and scores 54/79 = 0.684, and
the same cent wrong inside the delivered script costs the two rerun checks as
well, seven in all, for 44/79 = 0.557. A single misread rule costs more again:
rejecting the valid `quantity` of `0` drops 38 events, fails twelve checks and
scores 19/79 = 0.241. Doing nothing
scores 0.000 and writing the fourteen
files empty scores 1/79 = 0.013, so the curve separates a near miss from a total
miss across its whole range. The oracle expectation is
that running `solution/solve.sh` inside the container drives every positive
Channel A check to pass and holds every negative check in its failing state.

## Root cause

**Acceptance is state, so the architecture is forced.** The gate asks whether
accepting this debit would leave the balance below the floor, and the balance is
the fold of everything already accepted for that counterparty. That single
sentence rules out the filter-then-fold pipeline, rules out deciding a record in
isolation, rules out any order but chronological, and rules out computing totals
before deciding membership. The only shape that works is one interleaved
accept-and-fold pass per counterparty in UTC instant order, with `event_id`
compared as text breaking the one shared instant the corpus carries. Measured:
the two-phase reference scores 0.241, the file-order fold 0.177, the no-gate
variant 0.241.

The reference expresses that walk as a stream rather than as buckets. It sorts
the whole resolved set once by `(counterparty_id, utc_instant, event_id)`, which
lays every holder's run down in one contiguous block, then walks the runs with
`itertools.groupby` and yields one verdict per event, closing each run with a
marker carrying the balance it came to rest at. The closing total is then summed
over every holder the contract names, falling back to a holder's own opening
balance when the walk never reached it because it carries no events. Bucketing
the records into a dict first and folding each bucket is an equally correct way
to say the same thing; what neither shape may do is decide a record before the
records ahead of it have moved the balance.

**Decimal discipline, once, at the last moment.** `Decimal(str(value))` is the
entry point; constructing a `Decimal` from a float carries the float's error into
the exact arithmetic and defeats the point. The chain is gross times rate times
100, quantized once under the mode `policy.ini` names, then cast to `int`.
`ROUND_HALF_EVEN` is Python's context default and is not what the contract asks
for; the difference shows up on exactly the values that land on a half cent, and
this corpus is seeded to hold six hundred and eighty of them among the accepted
events.

**Order has to be derived, not inherited.** Every event file is shipped
shuffled, the ladder order is the UTC instant with `event_id` breaking a tie,
and `normalized.jsonl` is sorted by `event_id` as text. Three different
orderings, none of them file order, and the UTC instant itself only exists after
the timezone shift. A pipeline that folds in file order scores 0.177.

**Skip, orphan and block are three different outcomes.** A skipped event failed
to parse or failed a lookup and is counted against its file. An orphan refund
parsed fine but points at a sale id absent from `sales.csv` and is reported by
id. A blocked event parsed fine, resolved fine and was refused by the gate, and
is reported by id and counted per file, region and segment. All three stay out
of `normalized.jsonl` and out of every money total, and collapsing any two of
them into one bucket fails `data_quality_ledger_is_exact` plus every roll-up.

**Buckets are fixed, not discovered.** The five top level regions and four
segments are constants of the contract, and all nine files are written every
run. The west subtree is dormant in this corpus precisely so that enumerating
what the data contains yields a missing file.

**Determinism requirements.** Sets are unordered, dicts preserve insertion
order, and `Path.iterdir` returns whatever the filesystem hands back. Every one
of those has to be funnelled through `sorted()` before it reaches an artifact:
the `counterparties` array in each bucket, the keys of every `by_*` map, the
`products` array, `input_files`, and all three id lists. Nothing may carry a
timestamp, a `uuid` or a random value.

**Red lines.** No embedded shipped records or answers; no hardcoded input or
output paths; no shelling out and no third-party imports; no writes outside the
output directory; no non-deterministic ordering or content; no online lookup.

## Solution shape

1. Read the input and output directory from `sys.argv`, falling back to the
   `INPUT_DIR` and `OUTPUT_DIR` environment variables and then to `/app/data`
   and `/app/out`. Everything downstream is expressed relative to those two.
2. Load `policy.ini` first: the per segment floors, the opening rate date, the
   rounding mode, the grams per kilogram, and the two labels.
3. Build the reference tables from whatever is in the input directory:
   counterparty to segment, postal code, opening minor units and opening
   currency, keeping the row with the greatest `updated_at` and breaking a tie
   on the later row; postal prefix to region and default currency, plus region
   to parent so the top level ancestor can be walked; sku to category and unit
   mass; terminal to channel group, both sides trimmed and case folded;
   warehouse to postal code and timezone offset; sku to summed stock grams;
   `(date, currency)` to rate plus a sorted date list per currency for the
   carry-forward search; and the fiscal period spans.
4. Build the winning correction per `(event_id, field)` from `corrections.log`.
5. Walk the four event files in a fixed order, yielding raw mappings. Apply
   every correction that names the event and a column of its own file, before
   any parsing. Pull a refund's `sale_event_id` and send it to the orphan list
   when it is non-empty and absent from the raw sales ids.
6. Resolve each surviving raw mapping into the canonical sixteen-key record:
   lookups, timezone shift to UTC, date construction that rejects an impossible
   day, dated rate with carry-forward, sign convention per source, and the one
   quantized money expression. Any failure increments that file's skipped tally
   and the event disappears.
7. Run the ladder over the resolved records: one pass per counterparty in
   `(utc_instant, event_id)` order, opening at that counterparty's own opening
   balance and applying the gate event by event, collecting accepted records,
   blocked records and the balance each counterparty rests at. Sum those
   resting balances over every counterparty the contract names, including the
   ones that carry no events at all.
8. Sort the accepted records by `event_id` and write `normalized.jsonl` as
   compact sorted-key JSON, one record per line.
9. Fold the accepted records into `summary.json`, then write
   `data_quality.json` from the file listing, the three tallies and the three
   sorted id lists, then `product_summary.json` by walking the catalogue in sku
   order, then the five region files and the four segment files through one
   shared routine parameterised by the grouping key.
10. Return the nine closing figures and print them, so the closing message can
    quote them.

## Ordered plan

1. Read `schema.md` end to end, then open all thirteen input files and confirm
   the contract against the bytes: the tab delimiter in `refunds.tsv`, the
   comment lines and accented latin-1 memos in `legacy.txt`, the correction and
   noise lines in `corrections.log`, the repeated sku rows and the timezone
   column in `inventory.csv`, the `parent_region` chains in `regions.csv`, the
   gap dates in `fx_rates.csv`, and the four floors in `policy.ini`. Rubric R13
   credits exactly this, and R11 credits taking the constants from the policy
   file rather than retyping them.
2. Write down the four sign conventions and the one money routine before writing
   a parser. Implement the money routine first and test it by hand on a value
   that lands on a half cent, checking that it rounds away from zero rather than
   to even. Rubric R12 credits that discipline.
3. Build the reference tables, then the record resolver, then run it and read
   `normalized.jsonl`. Verify a sale, a refund, an adjustment and a legacy row
   individually against arithmetic done by hand, including one row whose
   warehouse offset moves it to the previous or next UTC day.
4. Only then write the ladder. Confirm on one stressed counterparty, by hand,
   that a blocked debit leaves the balance standing and that the next debit is
   judged against that standing balance. Rubric R10 credits the single
   interleaved pass.
5. Add the aggregates one artifact at a time, checking after each that
   `sum(by_region.values())`, `sum(by_segment.values())`, `sum(by_kind.values())`,
   `sum(by_category.values())`, `sum(by_channel_group.values())`,
   `sum(by_fiscal_period.values())` and `sum(by_source.values())` all equal
   `total_usd_cents`. Any inequality means an event is double counted or
   dropped.
6. Run the transform explicitly with both directories on the command line, into
   a directory that is not `/app/out`. Rubric R14 credits that run.
7. Copy the book to a scratch directory, shuffle the rows of the event files and
   the reference tables whose order the contract leaves free, and rerun. The
   artifacts must come out byte identical. Leave `counterparties.csv` and
   `corrections.log` alone, because their tie-breaks name file order. Rubric R15
   credits this second corpus.
8. Compute the nine closing figures from the run and close with a message that
   states all nine and names where each artifact was written. Rubrics R1 through
   R9 and R16 credit exactly that message.

## Pitfalls

- **Filtering the breaching debits and then folding the survivors.** The gate is
  a feedback loop, not a predicate. Scores 0.241, starting with
  `collateral_gate_blocks_exactly_the_right_events`.
- **Treating the gate as terminal.** A block does not close the counterparty.
  Later events are judged against the balance the block left standing, and
  positive events in between raise it again.
- **Folding in file order.** The event files are shipped shuffled and the ladder
  order is the UTC instant with `event_id` breaking a tie. Scores 0.177.
- **Ignoring the tie-break on a shared UTC instant.** One counterparty carries
  two events on the same instant, one of them a debit that the floor refuses
  only when it is taken first. Sorting by instant alone leaves the outcome to
  file order, which the shuffled rerun then contradicts.
- **Settling on the local date.** The warehouse offset moves two thousand one
  hundred and nine accepted events to a different UTC day, which moves the rate,
  the fiscal period and the ladder position. Scores 0.114.
- **Floats anywhere in the money path, or the default rounding mode.**
  `ROUND_HALF_EVEN` is the context default and the contract names half-up.
  Banker's rounding scores 0.304, float arithmetic 0.367, and both fail
  `half_cent_money_rounds_half_up`.
- **Serializing the money as a JSON float.** The contract says integer USD cents
  throughout, and the artifact comparisons compare JSON types as well as values,
  so `-45562.0` is not `-45562` and `11.0` is not `11`. A `Decimal` has to be
  cast to `int` before it reaches `json.dumps` rather than handed over with
  `default=float`, which is the usual reflex once `json.dumps` refuses a
  `Decimal`. Right values with float types score 0.430.
- **Quantizing before multiplying, or converting to USD and then to cents.**
  Two roundings where the contract asks for one, and the error is a cent per
  record, invisible per row and fatal once summed.
- **Passing `amount_minor` through as if it were USD cents.** It is minor units
  of the listed currency; it has to come back to currency units and go through
  the rate like everything else.
- **Applying corrections after parsing.** Some corrections repair a malformed
  row and some break a clean one, so the order is load bearing both ways.
- **Taking the nearest rate date instead of the most recent earlier one.** Three
  hundred and ninety-five accepted events sit on a gap, and fifty-one more name
  a currency quoted only later and are malformed.
- **Judging orphan links against accepted sales.** The rule names the rows of
  `sales.csv` as they stand. One hundred and five accepted refunds point at
  malformed sales rows and are not orphans.
- **Dedup by last row seen, or by first.** The winner is the greatest
  `updated_at`, and a tie goes to the later row. Forty-eight ties are seeded and
  each one moves a segment and therefore a floor.
- **Taking every region from the counterparty, or stopping at the first region
  name.** Only adjustments use the counterparty's own postal code, and the
  bucket is the top level ancestor, not the leaf.
- **Converting a blank currency as USD.** It is the matched prefix row's
  `default_currency`.
- **Accepting a signed or fractional quantity.** ASCII digits only, so `-4` and
  `1.5` are malformed, while `0` is valid and carries full money with zero
  units.
- **Reading `legacy.txt` as utf-8.** It is latin-1 and the accented memos raise.
- **Trusting a regex to validate a date.** `2028-02-30` passes a shape check and
  has a perfectly good rate; only real date construction rejects it, and
  `2028-02-29` beside it must be accepted.
- **Lowercasing a terminal without trimming it, or trimming without
  lowercasing.** The event files pad and recase terminal ids, and both halves
  are needed before the lookup.
- **Overwriting stock rows instead of summing them.** One sku, several
  warehouses. A plain assignment keeps the last one seen and the number looks
  plausible.
- **Multiplying grams by kilograms.** Stock is grams, the catalogue states
  kilograms, and `grams_per_kilogram` is in `policy.ini` for a reason.
- **Omitting `region_west.json` because nothing landed there.** All five regions
  and all four segments are written every run, with zeros and empty maps.
- **Dropping rows for an absent note or memo.** That is normal and never a
  reason to skip.
- **Keying `records_by_source` on bare stems.** The contract keys on the file
  name including its extension.
- **Pretty-printing the JSONL, or compacting the JSON.** The two serializations
  are different and `output_serialization_is_canonical` checks both.
- **Emitting a set, or an unsorted dict.** Every array and map must be sorted
  before serialization or `negative_nondeterministic_output` fires.
- **Finishing without the closing message.** Nine graded figures appear in no
  artifact, so skipping the message forfeits Channel B criteria R1 through R9.

## Provenance

```yaml
uuid: e08c051f-cce9-5aba-b20d-88fb75574b6c
instance_id: e08c051f-cce9-5aba-b20d-88fb75574b6c
task_name: terminal-bench/e08c051f-cce9-5aba-b20d-88fb75574b6c
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: f3bd3b5dc45704f32e4dbb08d4294247d33e8af270c229e1e4da9e102cb51b36  # informational; solve.py is 589 lines
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_verified_by: >
  Measured: the oracle transform scores every Channel A positive check and
  leaves all three negative checks unfired, for 79/79 positive weight and
  exactly 1.000 on the test channel; the judged channel has no oracle score. Six
  shortcut references were measured against the same channel: the
  filter-then-fold fold 0.241, a file-order fold 0.177, no gate at all 0.241,
  float money 0.367, banker's rounding 0.304, and settling on the local date
  0.114.
caveat: >
  The test channel carries 19 positive checks worth 79 weight and 3 negative
  checks worth -11 weight, so on its own it ranges -11/79 = -0.139 to +1.000.
  Four positives sit at weight 1, so a solver that lands only the mechanical
  shape checks is capped at 4/79 = 0.051. The judged channel carries 19 criteria
  worth 57 positive points, 2 of them negative and worth -8 together, so on its
  own it ranges -8/57 = -0.140 to +1.000. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward for this bundle runs from -0.135 to +1.000 with
  no clamp.
```
