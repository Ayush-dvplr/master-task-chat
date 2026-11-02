# TRUTH.md - 88ee425d-ca17-50cf-8d3e-86c3e62e06b6

## Defect

Nothing is broken here, everything is absent. `/app/data` holds thirteen input
files in seven formats (csv, tsv, jsonl, txt, log, json, ini) plus the written
contract `schema.md`, about thirty-two thousand three hundred lines in all, and
no code. The deliverable is a reusable transform plus thirteen exact artifacts
and a closing message carrying nine figures that no artifact holds. No file can
be skipped: a claim reaches its region, currency, rate, tariff period and lane
only through a chain that crosses every reference file, and whether the claim
clears at all depends on the state of its member's reserve ladder at the moment
it lands. The grading side reruns the delivered script against a relocated
copy, against a permuted copy with one currency's rate curve moved, and twice
over one unchanged copy, so every figure has to fall out of the rules rather
than out of the shipped bytes, and the same book has to clear to the same bytes
every time. Identifiers, amounts, currencies, floors and row counts are
specific to this instance, so nothing below can be recalled from training.

0. (focal) The reserve gate is a feedback loop, and it is the spine. Each
   member keeps one running reserve that opens at
   `opening_reserve_minor / 100` converted at the `[ladder] opening_rate_date`
   rate. Claims are then taken in order of UTC instant with `claim_id` breaking
   a shared instant. A non-negative claim clears and raises the reserve. A
   negative claim clears only when the reserve it would leave is at or above
   the `[reserve]` floor for that member's segment, and is otherwise reserve
   blocked: the reserve does not move, the claim leaves `normalized.jsonl` and
   every money total, and it is counted against its own file, region and
   segment. Acceptance of claim N therefore depends on the cleared fold through
   N-1, and blocking N changes the state that N+1 is judged against. The
   two-phase shape every weak solution reaches for, filter the breaching draws
   and then fold the survivors, cannot express this: the reference measured it
   at 0.241 against the oracle's 1.000, and dropping the gate altogether also
   lands on 0.241. Fifty-eight members carry two claims on a single UTC
   instant, so `claim_id` compared as text has to break the tie; taking the
   pair the other way round moves fifty-seven claims between cleared and
   blocked and shifts `total_usd_cents` by over four million cents.
1. (focal) Money is one exact decimal expression. The gross amount, the USD
   rate and the factor of 100 multiply together and the product is quantized
   exactly once under the `[rounding]` mode in `policy.ini`. The corpus is
   seeded so that five hundred and seventy-seven cleared claims land on an
   exact half cent, which is where half-up parts company with both float
   arithmetic and banker's rounding. Banker's rounding scores 0.367 and float
   arithmetic 0.367. Draws are negative, so half-up on them rounds away from
   zero, not toward it. The cents also have to reach the artifacts as JSON
   integers, because the artifact comparisons read types as well as values.
2. (focal) The resolution chain crosses every reference file and branches by
   source. Dispenses, recoveries and archive rows take their postal code from
   the dispensing depot in `stock_ledger.csv`; assessments take the member's
   own. `zones.csv` turns a postal prefix into a zone, and the reporting bucket
   is that zone's top level ancestor, reached by walking `parent_zone` through
   leaf, middle and top rows that are scattered across two thousand three
   hundred prefix rows. A blank currency falls back to the matched prefix row's
   `default_currency`, not to the ancestor's and not to USD, and only then can
   the dated rate be found.
3. (focal) Time is local at the depot and has to be moved to UTC before
   anything keys off it. `tz_offset_minutes` lives on every `stock_ledger.csv`
   row for that depot and may be negative; offsets in this corpus run from
   minus ten hours to plus twelve and include the quarter-hour cases. Three
   thousand and fourteen cleared claims change calendar day under the shift,
   which moves their rate lookup, their tariff period, their day bucket and
   their position in the ladder order. Clearing on the local date scores 0.304.
   Assessments already carry `Z` and must not be shifted at all.
4. (focal) `amendments.log` rewrites raw fields before any parsing happens.
   The winner per `(target, field)` is the greatest `utc_ts`, and a shared
   greatest timestamp is broken by the later line in file order. An amendment
   naming a field its target's own file does not have is ignored (one hundred
   and thirty such lines sit in the log), and an amendment naming no claim at
   all is reported in `unmatched_amendment_targets` (forty-five of them).
   Amendments cut both ways in this corpus: some turn a clean row malformed,
   some repair one, and forty-five of them move a recovery's link off the
   dispense file entirely and make it an orphan. Eight hundred and forty-five
   claim ids are amended in all.
5. (drift) Tariff periods come from the `periods` array in
   `tariff_calendar.json` as closed date spans, not from the calendar month.
   Thirteen twenty-eight day periods run 2030-10-01 to 2031-10-09 with a ten
   day hole between `TY31P06` and `TY31P07`, so three hundred and three cleared
   claims take the `unassigned_period` label rather than counting as an error.
6. (drift) `source`, `records_by_source`, `skipped_by_source` and
   `blocked_by_source` key on the input file name with its extension, and stock
   is in grams while the catalogue states mass in kilograms. Writing bare stems
   or multiplying grams by kilograms is the natural slip.
7. (trap) Orphan links are judged on the raw rows of `dispenses.csv`. A
   recovery whose `dispense_claim_id` names a dispense row that was itself
   skipped as malformed is still an ordinary cleared recovery, because the id is
   present in the file; two hundred and fourteen of them sit in this corpus
   waiting for a solver that checked against cleared dispenses instead. A
   `dispense_claim_id` that is whitespace only trims to empty and is not a link
   at all. The orphan test runs before any other field of the recovery is
   parsed and `schema.md` says so, because forty-five recoveries in this corpus
   are both orphan and otherwise unparseable: they carry a dead link and a
   quantity or depot that would have failed. Without that stated precedence
   those forty-five would sit in whichever bucket the solver guessed, and the
   guess moves `skipped_by_source`, `orphan_recovery_count` and both id lists
   at once, which is twenty-five of the seventy-nine positive points.
8. (trap) `members.csv` repeats ids: two thousand three hundred rows carry two
   thousand distinct members. The greatest `updated_at` wins and a shared
   greatest `updated_at` is broken by the later row in file order. Thirty ties
   are seeded, each with a different segment on the losing row, so a wrong
   tie-break moves the member between segment buckets and changes the reserve
   floor its whole ladder is judged against.
9. (trap) `quantity` is ASCII digits and nothing else. A signed value, a
   decimal point, a word, and a digit from another script are all malformed,
   and `quantity` of `0` is valid and contributes full money with zero units:
   two thousand six hundred and sixty-five cleared claims carry zero units,
   every assessment among them. `archive.txt` is latin-1 with accented bytes in
   its memos, so a strict utf-8 read of it raises before any of this matters.
10. (trap) Rates have gaps. Two thousand four hundred and sixty-nine cleared
    claims have no row for their currency on their clearing date and must take
    the most recent earlier row for that same currency; seventy-nine claims
    name a currency whose first quote is later than their clearing date and are
    malformed. Nearest-date matching and USD-at-one both produce confidently
    wrong cents.
11. (trap) One region bucket is dormant. The west subtree is documented in
    `zones.csv` and reachable through `parent_zone`, but no depot and no member
    sits on it, so `region_west.json` has to be written with zeros and empty
    maps. Enumerating the regions present in the data produces four correct
    files and one missing one.
12. (trap) `stock_ledger.csv` carries one row per stocking pair, so stock
    figures are sums across depots, and two hundred and three rows name sixty
    item codes the catalogue does not list, which belong in the closing report
    and in no artifact.
13. (trap) Three rules fire in narrow places, so a solver that reads the
    contract loosely loses them without seeing a pattern to warn it.
    `amendments.log` carries forty lines whose `field` is `claim_id`: that
    column identifies the claim and is never replaced, so a solver that treats
    every `field=` token as writable renames a cleared claim and breaks
    `normalized.jsonl`. Some rows in `recoveries.tsv` carry a negative
    `recovered_amount`, and the gross is minus the absolute value whatever sign
    the column holds, so a plain negation turns those draws into credits and
    sends them through the gate on the wrong side. And the sixty tie pairs land
    on a reserve exactly equal to the segment floor, which the contract clears
    rather than blocks, so a strict greater-than comparison blocks sixty claims
    that belong in the stream.

## Load-bearing work

The deliverable is one program, `/app/out/transform.py`, that takes an input
directory and an output directory and writes thirteen artifacts plus the nine
closing figures. It has to work on a directory it has never seen, so every
constant comes from `policy.ini` and every table from the reference files.

The nine steps of `schema.md` are not optional and not reorderable:

1. Amendments land on raw fields first. A claim is parsed once, after its
   winning amendments are applied, and never before.
2. The member row decides the segment, and for an assessment the postal code.
   Deduplicate `members.csv` by `(updated_at, row index)` before anything reads
   a segment, because the segment chooses the floor the whole ladder uses.
3. The postal code comes from the depot for three sources and from the member
   for the fourth. The depot also carries the UTC offset, on every one of its
   `stock_ledger.csv` rows.
4. The prefix is the text before the first `-`. `zones.csv` maps it to a zone
   and the reporting region is that zone's top level ancestor.
5. A blank currency falls back to the matched prefix row's `default_currency`.
6. The UTC instant is the local stamp minus the depot offset, except for an
   assessment, which is already UTC. The clearing date is the UTC date.
7. The rate is the row for `(clearing_date, currency)` or else the latest
   earlier row for that currency. No row on or before that date is malformed.
8. The lane is the gateway's lane, or the `assessment_lane` label.
9. `cleared_usd_cents` is `gross * rate * 100` quantized once, half up.

Then the ladder, which is the part that cannot be parallelised or filtered:
group the cleared candidates by member, order each group by
`(utc_instant, claim_id)`, open the reserve from the member's own row, and walk
the group carrying the reserve forward one claim at a time. Blocked claims do
not move the reserve and do not end the walk.

Then the artifacts. `normalized.jsonl` is ordered by `claim_id` as text, one
compact sorted object per line. The twelve `.json` documents are sorted keys,
two space indent, trailing newline. `summary.json` carries seven scalars and
seven money maps; `data_quality.json` carries the input inventory, three
per-source maps and three sorted id lists; `product_summary.json` carries one
entry per catalogue item in item code order, including items no claim touched;
the five region files and four segment files are written on every run, the
dormant one included.

## Verification

The test channel in this bundle registers nineteen positive checks worth
seventy-nine weight and three negative checks worth minus eleven. The oracle
clears every positive and fires no negative, for exactly 1.000.

Fifteen checks carry weight five and each one re-derives its own figure from
the input bytes rather than comparing against a stored answer:

- `reserve_gate_blocks_exactly_the_right_claims` rebuilds the ladder and
  compares the blocked id list, then asserts no blocked id reached the stream.
- `normalized_stream_is_exact` compares the whole stream record for record and
  type for type.
- `summary_totals_are_exact`, `region_rollups_are_exact`,
  `segment_rollups_are_exact`, `product_summary_is_exact` and
  `data_quality_ledger_is_exact` compare each document in full.
- `fx_carry_forward_and_predated_currency_are_exact` checks the cents of every
  claim that took an earlier rate, and that the cleared id set matches.
- `utc_day_shift_and_tariff_period_are_exact` checks date, instant and period
  for every claim whose UTC day moved, and for the whole stream.
- `member_dedup_segment_is_exact` checks the segment on every cleared record
  and that the underwater members exist.
- `half_cent_money_rounds_half_up` checks the cents of every claim whose
  product landed on the half cent.
- `orphan_links_use_raw_dispense_ids` checks the orphan list, that no orphan
  reached the stream, and that the stale-link recoveries did reach it with the
  right cents.
- `amendments_log_overrides_are_applied` checks the unmatched target list and
  the currency, quantity and cents of every amended claim that cleared.
- `reusable_transform_clears_a_relocated_book` runs the delivered script on a
  copy of the book in a different directory pair.
- `permuted_rows_and_shifted_rates_clear_identically` runs it on a copy whose
  rows are shuffled and one currency's whole rate curve is moved, then asserts
  the result matches the re-derivation for that copy and differs from the
  shipped totals.

Four checks carry weight one: `artifacts_exist`,
`output_serialization_is_canonical`, `data_quality_lists_every_input_file` and
`product_summary_lists_every_catalogue_item`. A solver that lands only those is
capped at 4/79 = 0.051.

Three checks carry negative weight and hold only when the named cheat is
present. `negative_hardcoded_sample_answers` holds when the shipped book's own
totals or ten of its member and item ids sit in the source.
`negative_network_dependency_or_shell_cheat` reads the parsed syntax tree of
the delivered program for a non-stdlib import, a network module or a shell
call. `negative_nondeterministic_output` runs the program twice over one
unchanged book and holds when any artifact's bytes differ.

Measured references against this channel: the oracle 1.000; a no-op 0.000; a
shape-only stub that writes every artifact with zeros 0.025; filter the
breaching draws and then fold 0.241; no gate at all 0.241; file order instead
of instant order 0.114; float money 0.367; banker's rounding 0.367; clearing on
the local date 0.304.

## Root cause

There is no bug to find. The task is a rebuild from a written contract, and
every way of losing points is a way of reading that contract loosely. The three
that cost the most are structural rather than arithmetic:

- Treating the gate as a predicate instead of a fold. The contract says the
  reserve a claim would leave decides it, and the reserve is whatever the
  cleared claims before it left behind. Any design that decides claims
  independently, or filters before folding, is wrong on every member that
  blocks anything, which is two hundred and eighty of them here.
- Keying anything off the local stamp. The depot offset has to be applied
  first, because the rate, the period and the ladder order all read the UTC
  value.
- Quantizing more than once, or at all before the final product. Both float
  arithmetic and banker's rounding part company with the contract on the five
  hundred and seventy-seven half-cent claims.

## Solution shape

`solution/solve.py` writes the program the instruction asks for to
`/app/out/transform.py`, runs it once over `/app/data`, and prints the nine
closing figures. The program itself is one file of plain standard library
Python:

- `Registry` loads `policy.ini` and all eight reference tables once, keeps the
  rate curve as a dict plus a sorted day list per currency for the
  carry-forward lookup, and exposes `head_zone`, `rate`, `span_of`, `cents` and
  `opening_cents`.
- `revisions` reduces `amendments.log` to the winning value per
  `(target, field)`.
- `harvest` yields `(source, raw mapping)` for every candidate line in file
  order, dropping blank and `#` lines from the archive and mapping an archive
  line with the wrong field count to an empty dict so it fails cleanly.
- `gross_of` carries the four sign conventions, one per source.
- `clear_claim` walks the resolution chain and returns the canonical record
  plus the three closing-report flags.
- `walk_ladder` is a generator: it sorts once by `(member, instant, claim_id)`,
  groups by member, and yields one verdict per claim while carrying the reserve
  forward. `run_ladder` drains it into cleared, refused and the closing total,
  adding the opening reserve of every member the walk never reached.
- `money_map`, `bucket` and `document` build and write the aggregates.

Money is `Decimal` end to end, quantized once per figure. Nothing reads a
clock, a random source or an unordered set, so two runs over one book produce
identical bytes.

## Ordered plan

1. Read `schema.md` end to end before looking at any row. It is the authority
   and it answers the precedence questions the data cannot.
2. List the input directory and open every file, including `policy.ini` and
   `amendments.log`. Fourteen files, four of them claims.
3. Load `policy.ini`: four floors, the opening rate date, the rounding mode,
   grams per kilogram, two labels.
4. Load the reference tables. Deduplicate `members.csv`. Build the prefix to
   zone map and the zone to parent map, and confirm the five top level zones
   resolve. Sum stock per item code across depots and note the item codes the
   catalogue lacks.
5. Reduce `amendments.log` to winners per `(target, field)`, and keep the set
   of targets that name no claim.
6. Stream the four claim files in order, applying amendments to own-file
   columns only, then test recoveries for orphan links against the raw dispense
   ids, then parse and resolve.
7. Count skips per source as they happen, and remember which dispense ids were
   skipped so the stale-link figure can be counted later.
8. Run the ladder per member in `(instant, claim_id)` order, carrying the
   reserve. Collect cleared, blocked and every member's closing reserve.
9. Sort the cleared records by `claim_id` and write `normalized.jsonl`.
10. Build and write `summary.json`, `data_quality.json`,
    `product_summary.json`, the five region files and the four segment files.
11. Rerun the program against a copy of the directory in another location and
    against a copy with the rows shuffled, and confirm the artifacts match.
12. Rerun it twice over one unchanged copy and compare the bytes.
13. Post the closing message with the nine figures and where each artifact
    landed.

## Pitfalls

- **Deciding each claim against the opening reserve.** The floor test reads the
  running reserve, which is the fold of everything cleared before it. 0.241.
- **Folding in file order.** The ladder is ordered by UTC instant, with
  `claim_id` as text breaking a shared instant. 0.114.
- **Blocking a claim that lands exactly on the floor.** The contract clears at
  or above the floor; sixty claims sit exactly on it.
- **Letting a blocked claim stop the member's walk.** Later claims are judged
  against the reserve the block left standing.
- **Shifting an assessment's stamp.** It already carries `Z` and has no depot.
- **Taking the region from the member for every source.** Only assessments use
  the member's postal code.
- **Stopping the zone walk at the first parent.** The reporting bucket is the
  top level ancestor, two or three hops up.
- **Falling back to USD for a blank currency.** The fallback is the matched
  prefix row's `default_currency`.
- **Nearest-date rate matching.** Only the exact date or the most recent
  earlier date for that same currency.
- **Treating an unquoted currency as an error-free zero.** It is malformed and
  counts against its own file.
- **Negating `recovered_amount` instead of taking minus its absolute value.**
  Some rows are already negative.
- **Accepting `quantity` written as `3.0`, `-4` or in another script.** ASCII
  digits only; `0` is valid and carries full money with no units.
- **Reading `archive.txt` as utf-8.** It is latin-1 and its memos carry
  accented bytes.
- **Dropping an archive line with twelve fields into a partial record.** Only
  exactly eleven fields carry a claim.
- **Accepting a float `amount_minor`.** It must be a JSON integer; `12.5` and
  `"1200"` are both malformed.
- **Applying an amendment whose field belongs to another file, or one naming
  `claim_id`.** Both are ignored, and the second renames a cleared claim.
- **Judging orphan links against cleared dispenses.** The test reads the rows
  of `dispenses.csv` as they stand.
- **Counting an orphan among its file's skips.** Orphan wins over malformed.
- **Omitting the dormant region file, or the segment file with no blocks.** All
  five region files and all four segment files are written every run.
- **Multiplying grams by kilograms.** `net_mass_grams` is net units times
  `pack_mass_kg` times `grams_per_kilogram`, quantized once.
- **Emitting cents as floats.** The artifact comparisons read JSON types, so
  `-45562.0` is not `-45562`.
- **Letting a set, a dict insertion order or a clock reach the output.** Every
  map and list is sorted before serialization, or the artifact differs run to
  run and `negative_nondeterministic_output` fires.
- **Reaching for `subprocess`, `requests` or `pandas`.** The grading image has
  neither the packages nor the network, and
  `negative_network_dependency_or_shell_cheat` reads the parsed source.
- **Pasting the shipped book's totals or ids into the program.**
  `negative_hardcoded_sample_answers` reads the source for both.

## Provenance

```yaml
uuid: 88ee425d-ca17-50cf-8d3e-86c3e62e06b6
instance_id: 88ee425d-ca17-50cf-8d3e-86c3e62e06b6
task_name: terminal-bench/88ee425d-ca17-50cf-8d3e-86c3e62e06b6
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: fc75ea4adac214bba3f2a2cf9d2f4dfa692a5c85b40b4db8d1c57457120ef35b  # informational; solve.py is 592 lines
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_verified_by: >
  Measured: the oracle transform scores every Channel A positive check and
  leaves all three negative checks unfired, for 79/79 positive weight and
  exactly 1.000 on the test channel; the judged channel has no oracle score.
  Eight shortcut references were measured against the same channel: a no-op
  0.000, a shape-only stub 0.025, the filter-then-fold fold 0.241, no gate at
  all 0.241, a file-order fold 0.114, float money 0.367, banker's rounding
  0.367, and clearing on the local date 0.304.
caveat: >
  The test channel carries 19 positive checks worth 79 weight and 3 negative
  checks worth -11 weight, so on its own it ranges -11/79 = -0.139 to +1.000.
  Four positives sit at weight 1, so a solver that lands only the mechanical
  shape checks is capped at 4/79 = 0.051. The judged channel carries 19
  criteria worth 61 positive points, 2 of them negative and worth -8 together,
  so on its own it ranges -8/61 = -0.131 to +1.000. tests/reward.toml divides
  each channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward for this bundle runs from -0.135 to +1.000
  with no clamp.
```
