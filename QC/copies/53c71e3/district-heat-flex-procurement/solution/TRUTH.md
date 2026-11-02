# TRUTH.md - district-heat-flex-procurement

## Defect

There is no broken program to repair. `/app/data` holds one season of a district-heating
demand-response programme: 500 events, 10,000 site rows, 18,014 offers with 108,036
interval profile rows, feeder ceilings, targets, segment floors, rate cards, waivers,
grant weights, pools and an export receipt, spread over fourteen files in seven formats
(ini, json, jsonl, csv, tsv, fixed-width txt, xml), plus the contract `/app/data/schema.md`. The solver
writes one stdlib program, `/app/out/derive_report.py`, that turns any extract in this
schema into nine exact JSON reports. Every rule is written in schema.md or in the comment
lines of `program.ini`, `rate_cards.xml` and `export_manifest.tsv`, which schema.md names
for the fields they govern. The shipped
extract is small and well behaved, so a program can produce plausible reports on it and
still be wrong on the extracts it is rerun on, which hold event-regions of up to eight
sites with up to three offers each, rejected rows and the combinations below.

1. (focal) Register readings. `profiles.tsv` holds meter register readings and a
   `register_multiplier` per row (schema.md section 1, profiles.tsv). A row's Wh is the
   reading times the multiplier, and that Wh becomes ticks under 2.3. The export receipt
   `export_manifest.tsv` sums `relief_wh` and `recovery_wh` as written, so a program that
   drops the multiplier matches the receipt exactly, while the correct reading does not
   match it on the 5,410 shipped rows whose multiplier is 2 or 5. Multiplying the reading's
   ticks instead of its Wh gives other ticks when the product is not a multiple of
   `wh_per_tick`. Caught by `register_multiplier_case`, `wh_per_tick_mutation` and every
   document of the four composed extracts.
2. (focal) Rate composition. The rate before cap is the card's start rate (`override` when
   the card has one, else `base`, per the rate_cards.xml comment) plus the event's uplift
   (events.json description) plus the segment's adder (`[segment_rate_adders]`, per the
   program.ini comment); the cap of 2.5 binds that sum. The receipt sums `base` only.
   Taking an override as the whole rate, skipping the adder, ignoring the override or
   adding the adder after the cap each give other credits, cap-binding counts, funded
   pools and grants. Caught by `rate_composition_case`, `segment_rate_adder_mutation` and
   the composed documents.
3. (focal) Interval credit rounding. The rate_cards.xml comment defines an offer's
   `credit_cents` as the sum of its interval amounts, each rounded half to even to whole
   cents. Rounding once per offer, or half up, gives other credits. Caught by
   `interval_credit_rounding_case` and the composed documents.
4. (focal) Exact portfolio choice. Section 5 picks the portfolio with the smallest
   five-component key (shortfall, floor deficit, blended cost, overdelivery, offer count)
   under per-interval relief and recovery ceilings and one mode per site, and counts the
   tied portfolios. An event-region has at most 8 x 3 offers, so at most 4^8 portfolios;
   plain enumeration that cuts at the ceilings finishes in well under a second. A greedy
   or first-fit choice fails. Caught by every region and segment document check on the
   four composed extracts.
5. (focal) Funded grant pools. Section 7 orders the work: portfolio, credits, funded pool,
   apportionment. The pool that is shared is the `pools.txt` pool minus the event-region's
   credit cents, floored at 0, so grants depend on the chosen portfolio and on every
   credit rule. Caught only through the composed extracts (region and audit documents);
   no isolated check reads it.
6. (focal) Rejected rows. `profiles.tsv` rows are sorted, in file order, into orphan,
   out-of-range and duplicate rows, in that order of precedence; a site row with an
   unknown region code is skipped with all its lines, and its offers become orphan offers.
   Writing rows straight into an interval list keeps the last duplicate, wraps interval 0
   onto the last interval and crashes on an interval above the count. Caught by
   `rejected_profile_rows_case` and the data-quality documents of the composed extracts.
7. (drift) Per-value ticks inside the search. Section 2.3 turns every Wh value into ticks
   before it is added, and section 5 compares relief, recovery, ceilings, targets and floors
   in ticks. A search that adds raw Wh and converts the sum reports correct ticks yet picks
   a different portfolio when values are not multiples of `wh_per_tick`. Caught by
   `tick_feasibility_case` and the composed extracts.
8. (drift) Waived recipients. A recipient site row counts its `grant_weight` twice when its
   compliance label is `CONTINUITY_WAIVED`, and the label follows the ranking of 2.6, so a
   site with a valid waiver that is on safety hold or in cooldown counts once. Doubling from
   the raw waiver fields, or doubling the whole beneficiary, gives other grants. Caught by
   the region documents of the composed extracts.
9. (decoy) `program.ini` carries an `[export]` section with `waiver_signed = Y`, a default
   of the legacy export tool. Schema section 1 says that section carries no rule, and section 2.6 makes a waiver valid only when `waiver_signed` is `Y`,
   so a blank value is not signed. The shipped waiver file holds 9 critical public rows
   with a pending certificate, a `VALID` status and a blank signature, and 21 such rows
   with `Y`. A program that applies the default labels the blank ones `CONTINUITY_WAIVED`.
   Caught by `waiver_labels_case` and the label, grant and audit documents.
10. (trap) H1, compliance ranking: a pending certificate with a valid signed waiver on a
   critical public site is `CONTINUITY_WAIVED`; a hold ranks above a cooldown above a
   waiver above a pending certificate above clear. `waiver_labels_case` (five site rows)
   and the composed extracts.
11. (trap) H2, the greatest sorted offer-id tuple wins among equal portfolios:
   `tie_break_greatest_tuple_case` and the composed extracts.
12. (trap) H3, the cap binds the whole rate before cap: `rate_composition_case` and the
    composed extracts.
13. (trap) H4, leftover cents among equal remainders go in descending beneficiary id, and a
    beneficiary with weight 0 receives nothing and is not listed:
    `residual_ties_descending_id_case` and the composed extracts.
14. (trap) H5, quantise when first derived: segment relief and credit totals on the composed
    extracts (5 Wh and 15 Wh make 3 segment ticks, not 2).
15. (trap) Component order: cost is compared before overdelivery, overdelivery before offer
    count, and offer count last. `objective_component_order_case`.
16. (omission) Section 7 gives the no-recipient pool and then says "for every other
    event-region" the funded pool is shared by largest remainder; an event-region whose
    recipients all weigh 0 (W of 0) has an unallocated pool only by section 9's
    `unallocated_pool_count` wording and by the allocation arithmetic. A program that
    divides by W crashes on such an extract and loses every document of it.

The shipped data never triggers a tie (item 11), a Wh value that is not a multiple of
`wh_per_tick` (items 1, 7 and 14), a repeated, out-of-range or unknown-region row (item 6),
a decision made by offer count alone (item 15), an override on a site row with a non-zero
adder (item 2: its 226 overrides are all on commercial cards, adder 0), or a written
example of an interval credit (item 3), and every event-region has at most five sites. It
does exercise the register multiplier (5,410 rows with 2 or 5), binding caps (395 chosen
offers), the label ranking (items 8, 9 and 10: 18 `CONTINUITY_WAIVED` rows), funded pools,
equal remainders, zero-weight beneficiaries, the order of objective components 3, 4 and 5
and 89 unallocated pools. The shipped data rejects only 14 orphan offers and their 36
orphan profile rows. No shipped file states a report figure.

Out of bounds: writing report values as literals or copying the shipped reports
(`negative_hardcoded_sample_answers`); naming grader paths in the program
(`negative_reads_tests_or_reward_files`); third-party or network imports
(`negative_external_dependency_or_network`); and claiming a check passed that the
trajectory shows failing or never run (judge R8).

## Load-bearing work

Ten artifacts are collected, and every one of them is graded:

- `/app/out/derive_report.py` - the deliverable. It is rerun by the verifier, as an
  unprivileged user with a 120-second limit per run, on four composed extracts and thirteen
  hand-built extracts (nine cases and two mutation pairs).
- `/app/out/summary.json` - global counts and totals in ticks and cents, and the `regions`
  and `segments` rollups; funded cents equal allocated plus unallocated.
- `/app/out/policy_audit.json` - label counts, one label per site row sorted by event and
  site, tie decisions with the tied portfolio count, cap-binding count, residual cents and
  residual-tie pool count.
- `/app/out/data_quality.json` - record counts for thirteen files, orphan, out-of-range and
  duplicate profile rows, unknown-region site rows, missing `waiver_signed`, ineligible
  offers, empty candidate groups and the two zero-denominator counts.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`,
  `region_East.json` - one entry per event: candidate count, chosen offer ids, per-interval
  quantities, bid cost, credit, pool, funded pool, allocated and unallocated cents,
  beneficiary cents and compliance counts, plus a totals block.
- `/app/out/segment_commercial.json`, `segment_public.json` - one entry per event-region
  with the segment's chosen offers, energy, money, floor ticks and floor attainment in
  basis points, plus totals.

Every key name, type and ordering is stated in schema.md sections 8 and 9. All numbers are
JSON integers; no floats or booleans appear in any report.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier`, restricts `/tests`
and runs `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
Channel A is `tests/test_output.py`: 38 checks, positive weight total 113 and negative
weight total -13. Channel B is `tests/judge.toml`: 8 criteria, positive total 15 and
negative total -5. `tests/reward.toml` weighs each channel by 0.5 over its positive
total, so the reward runs from -1.0 to 1.0.

Format checks on the agent's own `/app/out` (4 points): `artifact_set_exists_and_parses`,
`canonical_serialization_and_integer_units`, `report_keys_match_schema` and
`report_arrays_in_schema_order` (1 each). The canonical check also needs a JSON integer at
every place the schema gives an integer field. No check compares values on the shipped data.

Every value check stages a world-readable copy of the program, reruns it as an
unprivileged user on an extract the verifier writes, kills every process the run left
behind, and compares the parsed reports with an independent reference written for the
verifier. Before comparing, each check confirms that the wrong reading of every rule it
names would change the document or observable it grades, so the extract really separates
the readings. Every check prints one `[check]` line with its outcome and, on a failure,
the first differing path or the reason the program run failed.

- Composed extracts (76): four seeded extracts with 12 to 16 events each, graded one
  document type per check. The grants extract (A) is dense in waivers, holds, overrides
  and pools; the search extract (B) in ties, twin and zero offers, register multipliers
  and groups of up to eight sites; the rejects extract (C) in repeated, out-of-range,
  orphan and unknown-region rows with rows reversed; the mixed extract (D) in all of these
  with shuffled rows. Hand-built events of the isolated cases are planted in each. Per
  extract: the four region files (5), both segment files (5), summary.json (3),
  policy_audit.json (3) and data_quality.json (3).
- One rule family each (27, 3 each): `waiver_labels_case`, `tie_break_greatest_tuple_case`,
  `residual_ties_descending_id_case`, `tick_feasibility_case`,
  `objective_component_order_case`, `rejected_profile_rows_case`, `register_multiplier_case`,
  `rate_composition_case`, `interval_credit_rounding_case`.
- Mutations of a governed constant (6, 3 each): `segment_rate_adder_mutation` (the public
  adder of program.ini moves the credits, the portfolios stay) and `wh_per_tick_mutation`
  (`wh_per_tick` moves the interval ticks). Isolated share of the positive weight: 33 of 113.

Negative tests (return True when the cheat is present): `negative_hardcoded_sample_answers`
(-5), `negative_reads_tests_or_reward_files` (-5), `negative_external_dependency_or_network`
(-3). The first two only fire when the program ran cleanly on a composed extract. Each fires
on a different act, and none shares a trigger with judge R8.

Channel B: R1 to R4 (3 each) judge whether the agent built its own extracts for the
receipt, the register multiplier, an override with an adder and a half-cent interval
amount and checked a figure on each; R5 (+1) judges the code (integer rounding helpers, no
float rounding of a reported figure); R6 (+1) reading the file comments before writing the
credit code; R7 (+1) a final clean run on /app/data; R8 (-5) a claimed check that the
trajectory contradicts. No oracle score exists for the judged channel.

The reference solution is designed to pass all 35 positive checks and trip none of the
three negatives.

## Root cause

**Rules compose.** Each rule of schema.md is simple alone. The difficulty is where they
meet: the tick rule of 2.3 inside the search of section 5, the credit rules of section 6
inside the funded pool of section 7, the label ranking of 2.6 inside the grant weights,
the tie rule of 2.4 inside a search with twin offers, and the row precedence of section 1
against the orphan rules. Each of these chains ends in a whole report file.

**Integer arithmetic only.** Ticks are half-up divisions of each Wh value (reading times
multiplier); each interval amount of a credit is `relief Wh * rate / (1000 *
millicents_per_cent)` rounded half to even, and an offer's credit is their sum; attainment is `10000 * relief / floor` rounded half up and capped at 10000.

**Eligibility and labels are separate.** Only `dispatch_authorized` removes offers. Labels
change nothing in the search or the credits; in grants they matter only through the
doubled weight of `CONTINUITY_WAIVED` rows.

## Solution shape

1. Read `program.ini` for units, the code maps keyed upper case and the segment rate adders;
   ignore `[export]`.
2. Load the files: events, site rows (unknown region codes skipped and counted), state,
   waiver, rate card and weight lines of known site rows, offers (orphans counted), profile
   rows sorted into orphan, out-of-range, duplicate or kept in file order, reading times
   multiplier, then per-value ticks; card overrides; the receipt's data rows; targets, fixed-width ceilings and pools, and floors resolved to region names.
3. Group candidate offers (authorized site rows only) by event-region and site.
4. For each event in id order and each region in name order, visit every choice of at most
   one offer per site depth first, cutting a branch when a running relief or recovery sum
   passes a ceiling. Give every complete portfolio its five-component key, keep the
   smallest, count the portfolios that share it and keep the greatest sorted id tuple; log a
   tie decision when the count exceeds 1.
5. Credit each chosen offer at `min(start + uplift + adder, cap)` mill-cents per kWh (start
   = override or base), one half-to-even rounding per interval amount; count cap-binding
   offers.
6. Fund the pool as `max(0, pool - credit cents)`, weigh recipients (doubled when
   `CONTINUITY_WAIVED`), share by largest remainder with leftover cents by remainder then
   descending id; no recipients or W of 0 leaves the funded pool unallocated.
7. Label every site row by the ranking in 2.6 and count labels per event-region.
8. Build region entries, segment entries with floor attainment, totals, the summary, the
   audit and the quality counts, and write nine files with sorted keys and a newline.

The reference is a Python 3.12 standard-library program (`solution/solve.py`, 512 lines)
that `solution/solve.sh` copies to `/app/out/derive_report.py` and runs on `/app/data`
and `/app/out`. Its search is plain depth-first enumeration. The verifier's own reference
was written separately: it merges partial portfolios on their full future-relevant state,
keeps both extreme id tuples per state, and carries switches for each wrong reading.

## Ordered plan

1. Read schema.md to the last section and list the conventions of section 2 next to the
   sections that use them.
2. Print sample records from every data file and check the `program.ini` codes against
   `sites.csv`; note which sections of `program.ini` the contract uses.
3. Write out the five ranking components and the final tie rule.
4. Implement parsing with the row precedence of section 1, the search, settlement, funded
   pools, grants and labels with descriptive function names, errors handled rather than
   swallowed and integer arithmetic throughout (R5).
5. Compare the search with a second calculation on small random event-regions, including
   twin offers that force ties.
6. Build tiny extracts where the cap binds, an override meets a non-zero adder, a
   multiplied reading is not a multiple of `wh_per_tick`, an interval amount is half a
   cent, remainders tie, values
   are not multiples of `wh_per_tick`, profile rows repeat or fall out of range, a region
   code is unknown and every recipient weighs 0, and run the program on them.
7. Run the final program on `/app/data` (R7) and close with a short report that states
   failing checks as failing (R8).

## Pitfalls

- Adding raw Wh inside the search and converting the sum: reports correct ticks on the
  shipped data but picks other portfolios on extracts with odd Wh values.
- Sharing the raw pool: changes the grants of every event-region whose credit is positive.
- Funding the pool from uncapped credits, or from credits summed before rounding.
- Doubling a waived weight from the waiver fields alone, or doubling the whole beneficiary.
- Reading `waiver_signed` as `Y` when it is blank because `program.ini` says so.
- Letting the last duplicate profile row win, using interval 0 as a Python index, or
  counting rows of orphan offers as orphan profile rows.
- Looking up an unknown region code with a dict index, or dividing by W when every
  recipient weighs 0: the program crashes on that extract and loses its documents.
- Treating `export_manifest.tsv` as proof that readings are Wh and dropping the multiplier.
- Taking an override as the whole rate, skipping the adder, or adding it after the cap.
- Rounding a credit once per offer, or half up.
- Capping the base and adding the uplift afterwards, keeping the smallest of equal
  portfolios, handing leftover cents to the smallest id, ranking a cooldown above a hold,
  or listing zero-weight beneficiaries.
- Comparing overdelivery before cost, or offer count before overdelivery.
- Emitting floats or booleans, unsorted keys, missing keys or no trailing newline.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: district-heat-flex-procurement
task_name: terminal-bench/district-heat-flex-procurement
fix_patch_sha256: 44b69de8729373024f622ac80e2b8b3ca922382596235799a85a7b037f00c222  # sha256 of solution/solve.sh
solve_py_sha256: 5d773d5c70d3d3b213d7849ff6617138aa26e63dd7a14301fafcb3cf30b509f5  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # no Harbor run recorded in this file
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Not measured here. Oracle and nop figures come from runs on the
  tests-only copy and cover the test channel only; the judged channel has
  no oracle score.
```
