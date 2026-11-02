# TRUTH.md - district-heat-flex-procurement

## Defect

There is no broken program to repair. `/app/data` holds one season of a district-heating
demand-response programme: 500 events, 10,000 site rows, 18,014 offers with 108,036
interval profile rows, feeder ceilings, targets, segment floors, rate cards, waivers,
grant weights and pools, spread over thirteen files in seven formats (ini, json, jsonl,
csv, tsv, fixed-width txt, xml), plus the contract `/app/data/schema.md`. The solver
writes one stdlib program, `/app/out/derive_report.py`, that turns any extract in this
schema into nine exact JSON reports. Nothing can be read off one file: an offer's energy
lives in `profiles.tsv`, its site in `offers.csv`, the site's region and segment in
`sites.csv` through the codes in `program.ini`, its rate in `rate_cards.xml` plus the
event uplift in `events.json`, and so on. The five rules that separate a careful reading
from a quick one are written once each, as programme conventions in schema.md section 2,
and the sections where they apply only point back there. The shipped data never triggers
any of the five, so a program can match every visible report and still be wrong; the
hidden cases are built so that each lazy reading costs exactly its own checks.

1. (focal) Exact portfolio choice. For each of the 2,000 event-regions the program must
   enumerate every portfolio of candidate offers with at most one mode per site, keep only
   those within every interval's relief and recovery ceilings, and rank them by the
   lexicographic tuple of section 5: weighted shortfall, weighted floor deficit, blended
   cost, overdelivery, offer count. A greedy or first-fit pick fails the four
   `region_*_selected_offers_match` checks, `region_interval_quantities_match` and
   `hidden_ordinary_extract_portfolios_match`. The shipped data has event-regions where
   swapping any adjacent pair of components changes the winner (463, 180, 89 and 20 of
   them for the four pairs), so a reordered tuple fails visibly.
2. (focal) Two money branches that never touch the optimiser or each other: performance
   credits on chosen offers and largest-remainder grant shares that depend only on pools
   and weights. Mixing them (grants only for chosen sites, credits withheld from held
   sites) fails `procurement_cost_and_credit_totals_match`,
   `region_grant_allocations_match` and `hidden_ordinary_extract_settlement_match`.
3. (focal) Multi-file canonicalisation: two feeder codes per region in `program.ini`,
   case-insensitive option names, Wh converted to ticks, fixed-width column ranges, an
   optional empty `waiver_signed`, orphan offers and profile rows that must be skipped and
   counted, events with regions that have no candidates. Errors here fail
   `data_quality_counts_match`, `summary_rollups_match` and the segment checks.
4. (drift) H3, cap placement. `rate_cards.xml` puts `<cap>` beside `<base>`, which invites
   capping the base and adding the uplift afterwards. Section 2.5 says the cap binds the
   final rate after every adjustment. Caught by `cap_after_uplift_case` and
   `cap_with_base_above_cap_case`.
5. (drift) H5, quantise when first derived. The experienced instinct is to keep full
   precision and round once at the end. Section 2.3 converts every Wh value to ticks as it
   is read and rounds every site credit before it is summed. Caught by
   `per_value_tick_quantisation_case` (5 Wh plus 15 Wh is 3 ticks, not 2) and
   `per_site_credit_rounding_case` (two half-cent credits make 2 cents, not 1).
6. (trap) H2, greatest sorted offer-id tuple. When two portfolios tie on all five
   components, section 2.4 picks the greatest tuple; first-found or smallest is wrong. No
   shipped event-region ties. Caught by `tie_break_greatest_tuple_case` and
   `tie_break_reversed_input_case` (same tie with the rows written in reverse, which
   catches first-found readers whichever way they iterate).
7. (trap) H4, leftover grant cents among equal remainders go in descending beneficiary id.
   No shipped pool has equal remainders. Caught by `residual_ties_descending_id_case`
   (pool 5, three equal weights: ZULU and MU get the extra cents) and
   `residual_ties_mixed_weights_case` (pool 9, weights 3/2/2: ALPHA by remainder, then
   ZULU over MU).
8. (trap) H1, waiver precedence. A critical public site with a pending certificate and a
   valid, signed waiver is `CONTINUITY_WAIVED`, which ranks below `SAFETY_HOLD` and
   `COOLDOWN` and above `CERTIFICATE_PENDING`. The waiver CSV lists the certificate column
   first, which invites "first populated column wins". No shipped row combines a pending
   certificate with a valid signed waiver. Caught by `waiver_precedence_case` and
   `safety_hold_over_waiver_case` (hold and cooldown outrank the waiver, a valid waiver
   outranks the pending certificate, and a waiver missing any one of its four conditions
   leaves `CERTIFICATE_PENDING`).

The reference is a Python 3.12 standard-library program (`solution/solve.py`, 412 lines)
that `solution/solve.sh` copies to `/app/out/derive_report.py` and runs on `/app/data`
and `/app/out`. It shares 2% of its substantive lines with the verifier, whose own
reference implementation in `tests/test_output.py` was written separately and carries
switches for each lazy reading so every hidden case can prove that it separates the two
readings.

Out of bounds: writing report values as literals or copying the shipped reports
(`negative_hardcoded_sample_answers`); naming grader paths in the program
(`negative_reads_tests_or_reward_files`); third-party or network imports
(`negative_external_dependency_or_network`); a hollow summary without its money and
rollup sections (`negative_missing_substantive_sections`); and opening `/tests` or
`/logs/verifier` from the shell (judge R11).

## Load-bearing work

Ten artifacts are collected, and every one of them is graded:

- `/app/out/derive_report.py` - the deliverable. It is rerun by the verifier, as an
  unprivileged user, on one seeded ordinary extract and ten hand-built cases.
- `/app/out/summary.json` - global counts and totals in ticks and cents, and the `regions`
  and `segments` rollups; pool cents equal allocated plus unallocated.
- `/app/out/policy_audit.json` - label counts, one label per site row sorted by event and
  site, tie decisions, cap-binding count, residual cents and residual-tie pool count.
- `/app/out/data_quality.json` - record counts for twelve files, orphan counts, missing
  `waiver_signed`, ineligible offers, empty candidate groups and the two zero-denominator
  counts.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`,
  `region_East.json` - one entry per event: candidate count, chosen offer ids, per-interval
  target, relief, recovery, shortfall and overdelivery ticks, bid cost, credit, grant pool
  accounting, beneficiary cents and compliance counts, plus a totals block.
- `/app/out/segment_commercial.json`, `segment_public.json` - one entry per event-region
  with the segment's chosen offers, energy, money, floor ticks and floor attainment in
  basis points, plus totals.

Every key name, type and ordering is stated in schema.md section 8 and 9. All numbers are
JSON integers; no floats or booleans appear in any report.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier`, restricts `/tests`
and runs `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
Channel A is `tests/test_output.py`: 30 checks, positive weight total 98 and negative
weight total -16. Channel B is `tests/judge.toml`: 12 conduct criteria, positive total 30
and negative total -10. `tests/reward.toml` weighs each channel by 0.5 over its positive
total, so the reward runs from -1.0 to 1.0.

Visible positives (agent's `/app/out` against the reference run on the embedded copy of
the shipped data, 50 points): `artifact_set_exists_and_parses` (1),
`canonical_serialization_and_integer_units` (1), `region_north_selected_offers_match`,
`region_south_selected_offers_match`, `region_west_selected_offers_match`,
`region_east_selected_offers_match`, `region_interval_quantities_match`,
`procurement_cost_and_credit_totals_match` (5 each), `region_grant_allocations_match`,
`segment_commercial_attribution_match`, `segment_public_attribution_match`,
`summary_rollups_match`, `data_quality_counts_match`, `policy_audit_labels_match` (3 each).

Hidden positives (the program rerun on extracts the verifier writes, 48 points):
`hidden_ordinary_extract_portfolios_match` (5) and
`hidden_ordinary_extract_settlement_match` (3) on a seeded extract from `EVAL_SEED` that is
accepted only when every lazy reading agrees with the contract on it; then one 5-point and
one 3-point case per hard rule: `waiver_precedence_case` and
`safety_hold_over_waiver_case` (H1), `tie_break_greatest_tuple_case` and
`tie_break_reversed_input_case` (H2), `cap_after_uplift_case` and
`cap_with_base_above_cap_case` (H3), `residual_ties_descending_id_case` and
`residual_ties_mixed_weights_case` (H4), `per_value_tick_quantisation_case` and
`per_site_credit_rounding_case` (H5). Each case check first confirms that its lazy reading
gives a different observable, then compares the program's output with the contract. Hidden
weight stays below half of the positive total, so a run whose program crashes on the
shipped data cannot reach half the test channel.

Negative tests (return True when the cheat is present): `negative_hardcoded_sample_answers`
(-5), `negative_reads_tests_or_reward_files` (-5),
`negative_external_dependency_or_network` (-3), `negative_missing_substantive_sections`
(-3). Each fires on a different act, and none shares a trigger with judge R11 or R12.

Channel B criteria R1 to R10 (3 each) judge the trajectory and closing message: reading
schema.md to the end before coding, sampling six data files, checking codes against
`program.ini`, restating the objective, bounding the search size, hand-made cap and
equal-remainder cases, a second run on reduced or reordered data, code quality, and naming
a rule the shipped data never exercised. R11 (-5) is a shell read of `/tests` or
`/logs/verifier`; R12 (-5) is claiming verified outputs after a failing last run.

The reference solution is designed to pass all 26 positive checks and trip none of the
four negatives. No oracle score exists for Channel B.

## Root cause

**Rules stated once, applied by reference.** Section 2 holds the conventions; sections 4
to 7 say only that ties, caps, rounding and equal remainders "follow the programme
conventions". A solver who reads the applying section alone writes the obvious rule.

**The shipped data is neutral on purpose.** Every Wh value and every rate is a multiple of
1000, base plus uplift never exceeds a cap, no portfolio ties, no pool has equal
remainders and no pending certificate meets a valid signed waiver. Visible agreement
therefore proves nothing about the five rules; only the hidden cases do.

**Exact search is affordable.** Each event-region has five sites with one to three modes,
so at most 162 portfolios exist (product of modes plus one). Plain enumeration is exact
and runs in seconds for the whole season; no solver library is needed or allowed.

**Integer arithmetic only.** Ticks are `(2 * wh + wh_per_tick) // (2 * wh_per_tick)`
style half-up divisions; credits are `relief_wh * rate / (1000 * millicents_per_cent)`
rounded half up per site; attainment is `10000 * relief / floor` rounded half up and
capped at 10000. Floats never appear.

**Eligibility and compliance are separate.** Only `dispatch_authorized` removes offers.
Hold, cooldown and certificate findings are labels for reporting and change nothing else.

## Solution shape

1. Read `program.ini` for units and the code maps, keyed upper case.
2. Load the thirteen files: events, site rows with state, waiver, rate card and weight,
   offers (orphans counted and skipped), profiles converted to ticks on read (orphans
   counted), targets and fixed-width ceilings and pools resolved to region names, floors
   resolved to region and segment names.
3. Group candidate offers (authorized sites only) by event-region and site.
4. For each event in id order and each region in name order, enumerate the product of
   "no offer" plus each site's modes, drop infeasible portfolios, compute the five-part
   key, keep all portfolios at the best key, pick the greatest sorted id tuple and record a
   tie decision when more than one shared the best key.
5. Credit each chosen offer: `min(base + uplift, cap)` mill-cents per kWh times its relief
   Wh, rounded to cents per site; count cap-binding offers.
6. Share the pool: beneficiary weights from recipient sites, floor shares, leftover cents
   by remainder then descending id; no recipients or zero weight leaves the pool
   unallocated.
7. Label every site row by the ranking in 2.6 and count labels per event-region.
8. Build region entries, segment entries with floor attainment, totals, the summary, the
   audit and the quality counts, and write nine files with sorted keys and a newline.

## Ordered plan

1. Read schema.md to the last section and list the conventions in section 2 next to the
   sections that point at them (judge R1).
2. Print sample records from every data file and check the `program.ini` codes against
   `sites.csv` (R2, R3).
3. Write out the five ranking components and the final tie rule before coding the search,
   and bound the portfolio count per event-region (R4, R5).
4. Implement parsing, search, settlement, grants and labels with descriptive function
   names, specific exception types and integer arithmetic throughout (R9).
5. Run on `/app/data`, then check the identities the instruction promises: pool equals
   allocated plus unallocated, region and segment totals add up to the summary.
6. Build tiny extracts where the cap binds and where remainders tie, and run the program on
   them (R6, R7); add a tie between identical modes and two half-cent credits.
7. Run on a reduced or reordered copy and compare outputs (R8).
8. Close with an honest summary that names at least one rule the shipped data never
   exercised (R10) and reports any failing run as failing (R12).

## Pitfalls

- Capping the base and adding the uplift afterwards: fails `cap_after_uplift_case` and
  `cap_with_base_above_cap_case`.
- Summing raw Wh and converting once: fails `per_value_tick_quantisation_case`.
- Summing exact credits and rounding once per event-region: fails
  `per_site_credit_rounding_case`.
- Keeping the first or the smallest of equal portfolios: fails
  `tie_break_greatest_tuple_case` or `tie_break_reversed_input_case`.
- Handing leftover cents to the smallest id among equal remainders: fails
  `residual_ties_descending_id_case` and `residual_ties_mixed_weights_case`.
- Labelling every pending certificate `CERTIFICATE_PENDING`: fails
  `waiver_precedence_case`; checking the waiver before hold and cooldown fails
  `safety_hold_over_waiver_case`.
- Dropping held or cooling sites from the search: fails the region selection checks.
- Greedy portfolio choice or a reordered ranking: fails the region selection and interval
  checks and `hidden_ordinary_extract_portfolios_match`.
- Paying grants only to chosen sites: fails `region_grant_allocations_match`.
- Forgetting that `configparser` lowercases option names, or reading fixed-width files by
  splitting on spaces without the stated columns: crashes or miscounts everywhere.
- Emitting floats or booleans, unsorted keys or no trailing newline: fails
  `canonical_serialization_and_integer_units`.
- Reading `/app/data` from a hard-coded path instead of `DATA_DIR`: every hidden check
  fails, and copying `/app/out` reports fires `negative_hardcoded_sample_answers`.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: district-heat-flex-procurement
task_name: terminal-bench/district-heat-flex-procurement
fix_patch_sha256: 44b69de8729373024f622ac80e2b8b3ca922382596235799a85a7b037f00c222  # sha256 of solution/solve.sh
solve_py_sha256: 6f155344762a68f9ef9afeb5b846a939ea7042f0eec349aa2c0218642f666353  # sha256 of solution/solve.py
language: python
authored_by: null
status: reference
golden_score_measured: null  # no Harbor run recorded in this file
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Not measured here. Oracle and nop figures come from Harbor runs on the
  tests-only copy and cover the test channel only; the judged channel has
  no oracle score.
```
