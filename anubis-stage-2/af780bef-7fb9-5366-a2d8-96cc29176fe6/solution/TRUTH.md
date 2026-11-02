# TRUTH.md - af780bef-7fb9-5366-a2d8-96cc29176fe6

The FY31 deposit-gated meter settlement book. `/app/data` holds thirteen data
files and the written contract `schema.md`; the program that read them is gone.
The deliverable is one reusable stdlib-only `transform.py` that settles any
directory it is pointed at into fourteen exact artifacts, plus a closing message
carrying thirteen figures that appear in no artifact.

## Defect

What a solver must get right, and what goes wrong when the contract is read the
easy way.

- The per account deposit ladder is a feedback loop, not a filter (focal). Each
  account carries a running balance in USD cents, a strike count and a service
  state. Events are taken in order of UTC instant, ties broken by `event_id` as
  text. Two accounts carry a pair of events on one shared instant, so the
  `event_id` tie-break decides a verdict rather than sitting idle: settling
  `AC-01201` at `2030-09-01T03:21:01Z` or `AC-00597` at `2031-05-16T02:02:03Z`
  in the wrong order accepts the rebate the ladder is meant to withhold, which
  moves the stream, the blocked list and every roll-up those events touch.
  A zero or positive event is accepted and raises the balance. A negative
  event is accepted only when the balance it would leave is at or above its
  segment minimum; otherwise it is withheld, the balance does not move and the
  strike count rises. The strike that reaches `strike_limit` suspends the
  account: that event is itself withheld and every later event of that account,
  positive or negative, is blocked as suspended. Event N+1 is judged against the
  state standing after event N, so one wrong cent moves the balance, flips which
  neighbours survive, suspends an account early or never, and shifts every
  roll-up those events touch. 1977 events are gate blocked across 464 of the
  1900 accounts (24.4%), and 197 accounts end suspended.
- Money is one exact decimal expression quantized exactly once, HALF_UP
  (focal). `gross * usd_rate * 100` is built whole and rounded at that point and
  nowhere earlier. 944 accepted events land exactly on the half cent, where
  float arithmetic, `round()` and banker's rounding all disagree with the
  contract, and negative products must round away from zero.
- The rate is the row on that exact date, else the row on the most recent
  earlier date (focal). 3309 accepted events reach back. A currency with no row
  on or before its settlement date is malformed, not approximated forward: 956
  rows are dropped for carrying a currency whose curve starts later. The
  opening rate date itself has no row for four opening currencies, so the
  opening balances also reach back, and nearest-date matching moves them.
- The reporting region is the top level ancestor of the zone a postal prefix
  names (drift). Zones run prefix to leaf to mid to top, so reading
  `parent_zone` once lands a third of the way up and yields a label that is not
  one of the five region files.
- Identity is case sensitive, labels are not (drift). `event_id`, `account_id`,
  `tariff_code`, `substation` and `postal_prefix` compare exactly after
  trimming; segments, zones, categories, kinds, channel groups and intake
  terminals fold case. 100 event rows carry a lower or title cased account id
  and are malformed for it, while terminals spelled in another case are fine.
- The surviving account row is the greatest `updated_at`, and a tie goes to the
  later row in file order (trap). 196 account ids repeat and 46 of those are
  exact `updated_at` ties whose two rows disagree on segment and opening
  deposit, so first-row or last-row dedup changes the minimum the ladder
  enforces and the segment every one of that account's records reports.
- The orphan test reads the amended `read_event_id` against the raw
  `meter_reads.csv` rows and runs before any other field of the rebate is
  parsed (trap). 104 rebates are orphans; 30 of them would otherwise have been
  skipped and are still orphans rather than malformed. 192 accepted rebates link
  to a meter read that was itself skipped, which leaves them ordinary.
- Amendments in `audit_trail.log` replace a field before parsing (trap). The
  greatest timestamp wins and a shared timestamp goes to the later line; an
  amendment naming a field outside its target's own event file is ignored, and
  so is one naming `event_id`. 935 event ids are amended, 44 pairs share a
  timestamp, 34 name a foreign field, 18 name `event_id`, and 70 unmatched
  targets are reported rather than applied. The contract settles the one case
  the two rules would otherwise pull apart: a legacy line without exactly eleven
  fields carries no event id for the match, so the 10 amendments naming such a
  line are unmatched even though each line still counts as a malformed event of
  `legacy_ledger.txt`. Reading it the other way yields 60 unmatched instead.
- `quantity` is ASCII digits and nothing else (trap). A sign, a decimal point, a
  word, an inner space, a fullwidth or superscript digit, or an empty string is
  malformed; `0` is legal and contributes money but no units. 397 rows across
  the four event files are wrecked this way, and 73 amendments rescue a wrecked
  quantity while 72 more destroy a clean one.
- A settlement date no cycle covers takes the `unassigned_cycle` label and is
  not an error (drift). The thirteen cycles leave 37 uncovered days that carry
  events.
- The UTC instant is the local stamp minus the substation's
  `tz_offset_minutes`, which may be negative (drift). 2262 accepted events land
  on a different calendar day than their own `read_ts` names, which moves their
  rate, their cycle and their place in the ladder order.

## Load-bearing work

- Read `policy.ini` for the four segment minimum deposits, `opening_rate_date`,
  `strike_limit`, the rounding mode, `litres_per_cubic_metre` and the two
  labels. None of those constants are repeated in the contract text.
- Build the reference tables: account dedup by `updated_at` then file order;
  prefix to zone and zone to parent for the hierarchy fold; tariff code to
  category and unit volume; intake terminal to channel group; substation to
  postal code and tz offset; fleet litres summed per tariff code; one rate per
  currency per day with a sorted day list per currency for the reach-back; the
  cycle spans.
- Apply the winning amendment per event id and field before parsing anything.
- Settle each event through account, postal code, zone, region, currency, UTC
  instant, settlement date, rate, cycle, channel group, category and money.
- Run the ladder per account in one chronological pass that carries balance,
  strikes and suspension forward.
- Emit the fourteen artifacts, then report the thirteen closing figures.

## Verification

`tests/test_output.py` carries the shipped book as zlib-compressed base64 and
rebuilds it in a temporary directory, because the verifier container never
receives `/app/data`. It then re-derives the entire settlement independently
from those bytes with its own ledger, its own ladder walk and its own rounding.
No expected answer is stored in the file, so the figures below cannot be read
out of the tests. Registered positive weight total: 79.

Fifteen weight-5 criteria, each re-deriving the figure it grades:

1. `deposit_gate_blocks_exactly_the_right_events` (>= 150 blocked, >= 50
   suspended): the blocked id list matches and none of those ids reached the
   stream.
2. `normalized_stream_is_exact`: record for record, and JSON type for type, so
   a float cannot stand in for integer cents.
3. `summary_totals_are_exact`: seven scalars and seven breakdown maps.
4. `region_rollups_are_exact`: all five files after the zone fold.
5. `segment_rollups_are_exact`: all four files, each carrying its own minimum.
6. `product_summary_is_exact`: fleet litres and catalogue volume joined per
   tariff code, including codes no event touched.
7. `data_quality_ledger_is_exact`: counts plus the blocked, orphan and unmatched
   amendment id lists.
8. `fx_carry_forward_and_predated_currency_are_exact`: at least 50 reach-backs.
9. `utc_day_shift_and_billing_cycle_are_exact`: at least 100 day shifts.
10. `account_dedup_segment_is_exact`: the surviving row's segment per record.
11. `half_cent_money_rounds_half_up`: at least 200 half-cent products.
12. `orphan_links_use_raw_read_ids`: at least 20 accepted stale links.
13. `audit_trail_amendments_are_applied`: at least 100 amended accepted events.
14. `reusable_transform_settles_a_relocated_book`: the agent's own
    `transform.py` is re-run against a copy in a fresh directory pair.
15. `permuted_rows_and_shifted_rates_settle_identically`: rows shuffled in every
    file whose order the contract leaves free, one currency's whole rate curve
    moved by 3.75%, truth re-derived from the permuted book, and the totals
    required to differ from the shipped book's.

Four weight-1 criteria cover `artifacts_exist`,
`output_serialization_is_canonical`, `data_quality_lists_every_input_file` and
`product_summary_lists_every_tariff_code`.

Three negatives price the cheat paths. `negative_hardcoded_sample_answers`
holds when the shipped book's own totals or ten of its ids sit in the delivered
source. `negative_network_dependency_or_shell_cheat` holds when the parsed
syntax tree of `transform.py` imports outside the standard library, reaches the
network or spawns a process, so prose in a comment cannot trip it.
`negative_nondeterministic_output` holds when two runs over one unchanged book
disagree on the bytes of any artifact.

`tests/judge.toml` carries the other half: 25 criteria, positive total 67 and
negative total 18. Thirteen of them, R1 to R9 with R22 to R25, grade the
thirteen closing figures that no artifact holds, so the judged channel owns them
outright and no test reads them. R10 to R15 watch how the agent worked: the
single stateful ladder pass,
the constants taken from `policy.ini`, the one quantize per money figure, the
transform invoked with explicit directories, the reordered second corpus. R16
asks for the artifact locations and R21 judges whether the delivered transform
is code a reviewer would accept, which no assertion can decide without grading
source tokens. R17 to R20 carry the negatives: inventing a requirement, claiming
an unrun check, claiming a contract rule the code leaves out, and stating a
figure the run contradicts.

Measured discrimination on the shipped book:

| solver | test score |
| --- | --- |
| oracle, `solution/solve.py` | 1.0000 (79 of 79), reproduced |
| naive: no ladder, nearest-date rates, predated treated as normal, float `round()`, first-row dedup, case-folded ids, orphans judged against the accepted set, amendments ignored | 0.0506 (4 of 79), author measurement, solver not shipped |

The naive solver writes all fourteen artifacts with canonical serialization, so
it keeps the four weight-1 criteria and loses every weight-5 criterion. It
accepts 11397 events against the true 8293, skips 1303 against 2578, reports 252
orphans against 104, and blocks nothing at all.

## Root cause

The book is heterogeneous on purpose and no file settles an event by itself.
Every figure the artifacts carry is the output of a chain that crosses four
reference tables and a policy file, and the acceptance decision at the end of
that chain is stateful per account. A solver that treats the corpus as four
tables to be concatenated, or acceptance as a property of a single row, cannot
produce any of the fourteen artifacts exactly: the money is wrong where the
rounding and the rate reach differ, the stream is wrong where the ladder blocks,
and the roll-ups inherit both.

## Solution shape

`solution/solve.py` writes `/app/out/transform.py` and runs it once over
`/app/data`, then prints the thirteen closing figures. The transform is organised
as:

- `Book`: every reference table, loaded once, with `rate`, `cycle_of`,
  `ancestor`, `cents` and `opening_cents` as the only lookups the rest of the
  code needs.
- `amendments`, `harvest`: the winning amendment map and the raw event stream in
  file order, one source and mapping pair per candidate line.
- `gross_of`, `settle`: per-source gross money and the full settlement chain,
  raising `Rejected` wherever the contract says malformed.
- `walk_ladder`, `settle_ladder`: the chronological per account walk that
  carries balance, strikes and suspension forward and yields one verdict per
  event plus a closing marker, drained into accepted, withheld and suspended.
- `money_map`, `bucket`, `document`: the roll-ups and the two serializations.

Decimal throughout, one `quantize` per money figure, integer cents everywhere
after that. Byte-stable: sorted keys, sorted maps, sorted id lists, no clock and
no entropy.

## Ordered plan

1. Read `schema.md` end to end, then every input file, before writing code.
2. Load `policy.ini` and the eight reference tables, including the account dedup
   and the per currency sorted rate days.
3. Build the winning amendment map from `audit_trail.log`.
4. Stream the four event files in file order, apply amendments, test rebate
   links against the raw meter read ids, then settle or reject.
5. Walk each account's accepted candidates in UTC order through the ladder.
6. Write `normalized.jsonl`, then the roll-ups that consume it, then the region,
   segment and tariff slices.
7. Re-run the transform against a relocated and reordered copy of the book and
   compare, then report the thirteen figures.

## Pitfalls

- Filtering the stream before folding it. Acceptance cannot be decided per row.
- Rounding twice, or rounding a float. Both break the half-cent rows.
- Letting a predated currency borrow a later rate instead of dropping the row.
- Treating a suspended account's positive events as acceptable.
- Counting the events a suspension blocked inside `withheld_value_usd_cents`,
  which covers withheld events only.
- Dropping a blocked event from its region and segment blocked tallies, or
  letting it into the money totals.
- Omitting an account with no events from `deposit_closing_usd_cents`.
- Writing a region or segment file only when the bucket drew something.
- Reporting the thirteen closing figures from a stale run rather than the final
  one.

## Provenance

```yaml
uuid: af780bef-7fb9-5366-a2d8-96cc29176fe6
instance_id: af780bef-7fb9-5366-a2d8-96cc29176fe6
task_name: terminal-bench/af780bef-7fb9-5366-a2d8-96cc29176fe6
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680
solve_py_sha256: a6e9716b7537410838a36c69647f8752e2bfd3c467f5b88b64236bbe98fcbb8b
language: python
```

Closing report figures of the shipped book, for reference:

| figure | value |
| --- | --- |
| `withheld_value_usd_cents` | -8686567833 |
| `suspended_accounts` | 197 |
| `carry_forward_rate_events` | 3309 |
| `day_shift_events` | 2262 |
| `amended_events` | 935 |
| `half_cent_events` | 944 |
| `underfunded_accounts` | 28 |
| `unlisted_capacity_litres` | 3833466 |
| `stale_link_rebates` | 192 |
| `withheld_event_count` | 1033 |
| `gate_blocked_accounts` | 464 |
| `carry_forward_rate_currencies` | 14 |
| `half_cent_negative_events` | 340 |

Book wide: 8293 accepted events, 2578 skipped, 1977 gate blocked, 104 orphan
rebates, total -4820744106 USD cents, 17905 net units.
