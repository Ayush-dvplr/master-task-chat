# TRUTH.md - district-heat-flex-procurement

## Defect

There is no broken program to repair. `/app/data` holds one season of a district-heating
demand-response programme: 500 events, 10,000 site rows, 18,014 offers with 108,036
interval profile rows, feeder ceilings, targets, segment floors, rate cards, waivers,
grant weights, pools, season allowances of 1,280 sites and an export receipt, spread over
fifteen files in seven formats (ini, json, jsonl, csv, tsv, fixed-width txt, xml), plus the
contract `/app/data/schema.md`. The solver writes one stdlib program,
`/app/out/derive_report.py`, that turns any extract in this schema into nine exact JSON
reports. Every rule is written in schema.md or in the comment lines of `program.ini`,
`rate_cards.xml`, `site_allowances.tsv` and `export_manifest.tsv`, which schema.md names
for the fields they govern. The shipped extract is small and well behaved, so a program
can produce plausible reports on it and still be wrong on the extracts it is rerun on,
which hold event-regions of up to eight sites with up to three offers each, sites that
take part in several events, rejected rows and the combinations below.

1. (focal) Season allowance ledger. The comment at the top of `site_allowances.tsv` says
   that events reach a site's allowance one at a time in the order of the instants at
   which they start (`dispatch_start` in events.json), events that start at the same
   instant following the programme conventions (2.4: descending identifier), and that the
   relief ticks of the site's offers chosen in events reached before are drawn from it. An
   offer whose total relief ticks exceed what remains is not a candidate (section 3).
   Reading the allowance as a fixed per-event limit, walking events by `event_id` or by
   the text of `dispatch_start`, or serving equal instants by ascending id gives other
   candidates, portfolios, credits, grants and quality counts. Caught by
   `allowance_order_case`, `allowance_consumption_case`, `allowance_ticks_mutation` and
   every document of the four composed extracts.
2. (focal) Rate composition. The rate of a site row starts from `override` when its card
   has one, else `base` (rate_cards.xml comment), plus the event's uplift (events.json
   description) plus the segment's adder (`[segment_rate_adders]`, per the program.ini
   comment); 2.5 makes the card's cap bind that whole rate. Dropping the uplift, ignoring
   the override or taking it as the whole rate, skipping the adder or adding it after the
   cap each give other credits, cap-binding counts, funded pools and grants. Caught by
   `rate_composition_case`, `segment_rate_adder_mutation` and the composed documents.
3. (focal) Interval credit rounding. The rate_cards.xml comment defines an offer's
   `credit_cents` as the sum of its interval amounts, each rounded half to even (2.2
   defines it). Rounding once per offer, or half up, gives other credits. Caught by
   `interval_credit_rounding_case` and the composed documents.
4. (trap) The export receipt, a control. `export_manifest.tsv` records the record count and one
   field sum per file as written. It agrees with any program that parses the files whole,
   whatever it does with multipliers, overrides or allowances; its rows are counted in
   `data_quality.json` and no report figure is taken from it.
5. (focal) Exact portfolio choice. Section 5 picks the portfolio with the smallest
   five-component key (shortfall, floor deficit, blended cost, overdelivery, offer count)
   under per-interval relief and recovery ceilings and one mode per site, and counts the
   tied portfolios. An event-region has at most 8 x 3 offers, so at most 4^8 portfolios;
   plain enumeration that cuts at the ceilings finishes in well under a second. A greedy
   or first-fit choice fails. Caught by every region and segment document check on the
   four composed extracts.
6. (focal) Funded grant pools. Section 7 orders the work: portfolio, credits, funded pool,
   apportionment. The pool that is shared is the `pools.txt` pool minus the event-region's
   credit cents, floored at 0. Caught through the composed extracts (region and audit
   documents).
7. (drift) Register readings. A profile row's Wh is the reading times its
   `register_multiplier`, and that Wh becomes ticks under 2.3. Caught by the composed
   extracts.
8. (drift) Rejected rows. `profiles.tsv` rows are sorted, in file order, into orphan,
   out-of-range and duplicate rows; a site row with an unknown region code is skipped with
   all its lines. Caught by the data-quality documents of the composed extracts.
9. (drift) Per-value ticks inside the search, waived recipients (weight doubled for a
   `CONTINUITY_WAIVED` label), the `[export]` decoy of `program.ini`, the compliance
   ranking, the greatest sorted offer-id tuple among equal portfolios, leftover cents in
   descending beneficiary id, quantise when first derived and the component order are
   planted in the composed extracts and graded through their documents.
10. (omission) An event-region whose recipients all weigh 0 (W of 0) has an unallocated
   pool only by section 9's `unallocated_pool_count` wording and by the allocation
   arithmetic. A program that divides by W crashes on such an extract.

The shipped data never separates the readings of items 1 to 3 that the hidden extracts
separate: every shipped allowance either covers all of its site's offers in every event
(1,226 sites) or is below each of them (54 sites, 730 blocked offers), so the walk order
and the drawing never change a shipped report; `dispatch_start` text order equals instant
order (offsets `+01:00` and `+00:00`), though start order differs from id order; no
shipped interval amount is an exact half cent; and the 226 overrides sit on commercial
cards with adder 0. It does exercise the register multiplier (5,410 rows with 2 or 5),
binding caps (382 chosen offers), the label ranking (18 `CONTINUITY_WAIVED` rows), funded
pools, equal remainders and 89 unallocated pools. No shipped file states a report figure.

Out of bounds: writing report values as literals or copying the shipped reports
(`negative_hardcoded_sample_answers`); naming grader paths in the program
(`negative_reads_tests_or_reward_files`); third-party or network imports
(`negative_external_dependency_or_network`); and claiming a check passed that the
trajectory shows failing or never run (judge R8).

## Load-bearing work

Ten artifacts are collected, and every one of them is graded:

- `/app/out/derive_report.py` - the deliverable. It is rerun by the verifier, as an
  unprivileged user with a 120-second limit per run, on four composed extracts and eight
  hand-built extracts (four cases and two mutation pairs).
- `/app/out/summary.json` - global counts and totals in ticks and cents, and the `regions`
  and `segments` rollups; funded cents equal allocated plus unallocated.
- `/app/out/policy_audit.json` - label counts, one label per site row sorted by event and
  site, tie decisions with the tied portfolio count, cap-binding count, residual cents and
  residual-tie pool count.
- `/app/out/data_quality.json` - record counts for fourteen files, orphan, out-of-range and
  duplicate profile rows, unknown-region site rows, missing `waiver_signed`, ineligible
  offers, allowance-blocked offers, empty candidate groups and the two zero-denominator
  counts.
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
Channel A is `tests/test_output.py`: 33 checks, positive weight total 98 and negative
weight total -13. Channel B is `tests/judge.toml`: 8 criteria, positive total 17 and
negative total -5. `tests/reward.toml` weighs each channel by 0.5 over its positive
total, so the reward runs from -1.0 to 1.0. Each output document is graded whole on fresh
inputs, as the instruction says.

Format checks on the agent's own `/app/out` (4 points, 4.1 percent):
`artifact_set_exists_and_parses`, `canonical_serialization_and_integer_units`,
`report_keys_match_schema` and `report_arrays_in_schema_order` (1 each). No check compares
values on the shipped data.

Every value check stages a world-readable copy of the program, reruns it as an
unprivileged user on an extract the verifier writes, kills every process the run left
behind, and compares the parsed reports with an independent reference written for the
verifier. Before comparing, each check confirms that the wrong reading of every rule it
names would change the document or observable it grades, so the extract really separates
the readings. Every check prints one `[check]` line with its outcome and, on a failure,
the first differing path or the reason the program run failed.

- Composed extracts (76, 77.6 percent): four seeded extracts with 12 to 16 events each,
  graded one document type per check. Sites take part in several events, events start in
  an order unlike their ids, with mixed UTC offsets and equal instants, and allowances are
  tight. The grants extract (A) is dense in waivers, holds, overrides and pools; the search
  extract (B) in ties, twin and zero offers, register multipliers and groups of up to eight
  sites; the rejects extract (C) in repeated, out-of-range, orphan and unknown-region rows
  with rows reversed; the mixed extract (D) in all of these with shuffled rows. Per
  extract: the four region files (5), both segment files (5), summary.json (3),
  policy_audit.json (3) and data_quality.json (3).
- One rule family each on a hand-built extract (12, 3 each): `rate_composition_case`,
  `interval_credit_rounding_case`, `allowance_order_case`, `allowance_consumption_case`.
- Mutations of a governed constant (6, 3 each): `segment_rate_adder_mutation` (the public
  adder of program.ini moves the credits, the bid costs stay) and
  `allowance_ticks_mutation` (one site's `allowance_ticks` moves the candidates and
  portfolios of later events, the compliance labels stay). Isolated share of the positive
  weight: 18 of 98.

Negative tests (return True when the cheat is present): `negative_hardcoded_sample_answers`
(-5), `negative_reads_tests_or_reward_files` (-5), `negative_external_dependency_or_network`
(-3). The first two only fire when the program ran cleanly on a composed extract. Each fires
on a different act, and none shares a trigger with judge R8.

Channel B: R1 to R4 (3 each) judge whether the agent built its own extract for a drawn
allowance, for events whose start order differs from their id and text order, for a
composed rate above its cap and for a half-cent interval amount, and checked the
observable each one moves; R5 (+3) the allowance ledger as one named function; R6 (+1)
exact arithmetic for every reported figure; R7 (+1) a final clean run on /app/data;
R8 (-5) a claimed check that the trajectory contradicts. No oracle score exists for the
judged channel.

The reference solution is designed to pass all 30 positive checks and trip none of the
three negatives.

## Root cause

**Rules compose.** Each rule of schema.md is simple alone. The difficulty is where they
meet: the allowance ledger, which carries the choices of earlier-starting events into the
candidates of later ones, the tick rule of 2.3 inside the search of section 5, the credit rules of section 6
inside the funded pool of section 7, the label ranking of 2.6 inside the grant weights,
the tie rule of 2.4 inside a search with twin offers, and the row precedence of section 1
against the orphan rules. Each of these chains ends in a whole report file.

**Integer arithmetic only.** Ticks are half-up divisions of each Wh value (reading times
multiplier); each interval amount of a credit is `relief ticks * wh_per_tick * rate
/ (1000 * millicents_per_cent)` rounded half to even, and an offer's credit is their sum; attainment is `10000 * relief / floor` rounded half up and capped at 10000.

**Eligibility and labels are separate.** Only `dispatch_authorized` and the allowance
remove offers. Labels
change nothing in the search or the credits; in grants they matter only through the
doubled weight of `CONTINUITY_WAIVED` rows.

## Solution shape

1. Read `program.ini` for units, the code maps keyed upper case and the segment rate adders;
   ignore `[export]`.
2. Load the files: events, site rows (unknown region codes skipped and counted), state,
   waiver, rate card and weight lines of known site rows, offers (orphans counted), profile
   rows sorted into orphan, out-of-range, duplicate or kept in file order, reading times
   multiplier, then per-value ticks; card overrides; site allowances (comment lines
   skipped); the receipt's data rows; targets, fixed-width ceilings and pools, and floors
   resolved to region names.
3. Group the offers of authorized site rows by event-region and site.
4. Walk the events in the order of their `dispatch_start` instants (equal instants in
   descending event id). For each event and region, drop the offers whose total relief
   ticks exceed what remains of their site's allowance (counted as blocked), choose the
   portfolio as in step 5, and after the event draw the chosen offers' relief ticks from
   their sites' allowances.
5. For each event-region, visit every choice of at most
   one offer per site depth first, cutting a branch when a running relief or recovery sum
   passes a ceiling. Give every complete portfolio its five-component key, keep the
   smallest, count the portfolios that share it and keep the greatest sorted id tuple; log a
   tie decision when the count exceeds 1.
6. Credit each chosen offer at `min(start + uplift + adder, cap)` mill-cents per kWh (start
   = override or base), one half-to-even rounding per interval amount; count cap-binding
   offers.
7. Fund the pool as `max(0, pool - credit cents)`, weigh recipients (doubled when
   `CONTINUITY_WAIVED`), share by largest remainder with leftover cents by remainder then
   descending id; no recipients or W of 0 leaves the funded pool unallocated.
8. Label every site row by the ranking in 2.6 and count labels per event-region.
9. Build region entries in event id order, segment entries with floor attainment, totals,
   the summary, the audit and the quality counts, and write nine files with sorted keys and a newline.

The reference is a Python 3.12 standard-library program (`solution/solve.py`, 549 lines)
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
   swallowed, the allowance ledger in one named function (R5) and integer
   arithmetic throughout (R6).
5. Compare the search with a second calculation on small random event-regions, including
   twin offers that force ties.
6. Build tiny extracts where one site's allowance is drawn by an earlier-starting event,
   two events start in an order unlike their ids and their text, two events start at the
   same instant written with different offsets, the cap binds, an override meets a
   non-zero adder and an uplift, a multiplied reading is not a multiple of `wh_per_tick`,
   an interval amount is half a cent, remainders tie, values
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
- Reading the allowance as a fixed limit per event, or walking events by `event_id` or by
  the text of `dispatch_start`: the shipped reports and the receipt look right, the
  extracts with shared sites and tight allowances do not.
- Serving events that start at the same instant in ascending id.
- Taking an override as the whole rate, dropping the uplift, skipping the adder, or adding
  it after the cap.
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
solve_py_sha256: fa10bcc9cdeb837e829869fd97dd95a7b991deacbb35b6e2a180d05ef644ce5a  # sha256 of solution/solve.py
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
