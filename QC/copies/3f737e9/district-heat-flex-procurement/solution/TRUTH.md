# TRUTH.md - district-heat-flex-procurement

## Defect

There is no broken program to repair. The extract holds one winter season of a district-heat
demand-response programme: 500 events, 10,000 site rows, 18,014 offers with 108,036 interval
profile rows, feeder ceilings, targets, segment floors, rate cards, continuity waivers, grant
weights, grant pools, season allowances of 1,280 sites and an export receipt, spread over fifteen
files in seven formats (ini, json, jsonl, csv, tsv, fixed-width txt, xml), plus the contract
`schema.md`. The agent writes one stdlib program, `/app/out/derive_report.py`, that turns any
extract in this schema into nine exact JSON reports. The rules live in `schema.md` and in the
comments of `program.ini`, `rate_cards.xml`, `site_allowances.tsv` and `export_manifest.tsv`;
`schema.md` says those comments are binding.

Focal items:

1. (focal) Grant apportionment with a minimum grant. `program.ini` `[grants]` gives
   `claim_cents_per_weight` (40) and `minimum_grant_cents` (25). Schema section 7: when the
   beneficiaries' claims fit in the funded pool F each receives its claim and the rest of F is
   unallocated; otherwise F is shared by largest remainder, a beneficiary whose share is below
   the minimum receives nothing, and every cent of F is shared again by largest remainder in
   proportion to weight across only the beneficiaries that kept the minimum. The second share is
   a plain largest-remainder share: it does not test the claims again. A program that routes the
   survivors back through the whole apportionment pays them their claims whenever those fit and
   leaves cents unallocated. Graded by `grants_match_hard`, `grant_allocation_match_hard`,
   `funded_pool_match_hard`, `residual_match_hard`, the four region totals, `summary_match_hard`
   and `minimum_grant_mutation`.
2. (focal) Carried cents. The unallocated cents of an event-region are carried into the
   funded pool of the same region's next event in season order (the ledger order of the
   `site_allowances.tsv` comment). Any grant error therefore moves every later funded pool,
   allocation and total of that region. The carried figure is stated plainly in section 7.
3. (focal) Allowance holders. `site_allowances.tsv` has a `draws_from` column. A site with a
   blank `draws_from` draws on its own allowance; a site whose `draws_from` names another site
   draws on the allowance that site draws on, so chains are followed to their end. Shipped data
   has 60 chains of one link; the hidden season extract has chains of two to four links with
   binding holder allowances. Graded by `selection_match_hard`, `intervals_match_hard`,
   `ledger_quality_match_hard`, `segment_rows_match_hard`, `tie_decisions_match_hard`,
   totals and `allowance_ticks_mutation`.
4. (focal) Credited relief. The `rate_cards.xml` comment bases each interval amount on the
   offer's credited relief ticks; schema section 6 defines them as relief ticks less recovery
   ticks of the same interval, never below 0. Shipped profiles have no interval with both relief
   and recovery, so the two readings agree there; the hidden extracts have many such intervals.
   Graded by `credit_rows_match_hard`, `segment_credit_rows_match_hard`, the funded pools and
   grants that depend on credits, totals and `segment_rate_adder_mutation`.
5. (drift) Season allowance ledger in start-instant order, equal instants in descending event id;
   rate composition (override or base, plus uplift, plus segment adder, then cap); per-interval
   half-to-even credit rounding; exact portfolio choice by the five components and the greatest
   sorted id tuple; register multipliers; rejected profile rows; per-value ticks; compliance
   labels; floor attainment. These are graded inside the family documents.
6. (trap) The export receipt counts records and sums fields as written. It agrees with the
   files whatever reading a program takes; no report figure comes from it.
7. (focal) Exact portfolio on wide event-regions. Schema section 3 bounds a site to at
   most 3 candidate offers in an event and every run to 120 seconds; it puts no bound on the
   number of sites. The four wide hidden extracts have 20 to 26 sites with candidates in every
   event-region, most sites with two offers of identical relief, recovery and cost, and targets
   that need most sites. The best portfolio, the greatest sorted id tuple among the tied ones
   and `tied_portfolio_count` (often thousands of tied portfolios) must be exact within the
   limit. A program that looks at tied portfolios one at a time runs past 120 seconds; a
   cheapest-first pick is feasible but not best. Graded by `wide_0_*` to `wide_3_*`.

## Load-bearing work

Ten artifacts are collected, and every one of them is graded:

- `/app/out/derive_report.py` - the deliverable. The verifier reruns it, as an unprivileged
  user with a 120-second limit per run, on the shipped data, on two seeded hidden extracts (a
  season extract with `draws_from` chains and planted grant pools, and a settlement extract with
  planted grant pools and no `draws_from` rows), on four seeded wide extracts and on three
  mutation pairs.
- `/app/out/summary.json` - global counts and totals and the `regions` and `segments` rollups.
- `/app/out/policy_audit.json` - label counts, site labels, tie decisions, cap-binding count,
  residual cents and residual-tie pool count.
- `/app/out/data_quality.json` - record counts, rejected-row counts, ineligible and
  allowance-blocked offers, empty candidate groups and the zero-denominator counts.
- `/app/out/region_North.json`, `region_South.json`, `region_West.json`, `region_East.json` -
  one entry per event with candidates, chosen offers, intervals, bid cost, credit, pool, funded
  pool, allocated and unallocated cents, beneficiary grants and compliance counts, plus totals.
- `/app/out/segment_commercial.json`, `segment_public.json` - one entry per event-region with
  the segment's chosen offers, energy, money, floor ticks and attainment, plus totals.

Every key, type and order is stated in schema.md sections 8 and 9. All numbers are JSON
integers.

## Verification

`tests/test_output.py` has 66 checks: 63 positive (237 points) and 3 negatives (-13).

- Owned-row families (160): twenty families, each a shipped-data check (w3) and a `_hard`
  check on a hidden seeded extract (w5). Each family owns its rows and compares them exactly,
  reporting the first differing path. Season extract families: `selection`, `intervals`,
  `tie_decisions`, `segment_rows`, `ledger_quality`, `region_totals_North`,
  `region_totals_South`, `region_totals_West`, `region_totals_East`, `segment_totals`,
  `summary`, `labels`, `quality_counts`. Settlement extract families: `credit_rows`,
  `segment_credit_rows`, `funded_pool`, `grants`, `grant_allocation`, `residual`,
  `cap_binding`.
- Mutations (9, w3 each): `segment_rate_adder_mutation`, `allowance_ticks_mutation`,
  `minimum_grant_mutation`; each pair differs in one governed input and the check requires the
  dependent figures to move as the reference says while fixed figures stay.
- Wide extracts (64): for each of the four wide extracts `wide_k_portfolios_feasible` (w3:
  every chosen set is candidate offers of the event-region, one per site, within both
  ceilings in every interval, and not empty where the optimal portfolio is not empty),
  `wide_k_selection_match` (w5), `wide_k_tie_decisions_match`
  (w5) and `wide_k_intervals_match` (w3), each compared whole.
- Format (4, w1 each) on the reports in `/app/out`: `artifact_set_exists_and_parses`,
  `canonical_serialization_and_integer_units`, `report_keys_match_schema`,
  `report_arrays_in_schema_order`.
- Negatives: `negative_hardcoded_sample_answers` (-5), `negative_reads_tests_or_reward_files`
  (-5), `negative_external_dependency_or_network` (-3). The program must use only the
  Python 3.12 standard library.

Figures the families read include `credit_cents`, `unallocated_pool_count`, the
`CONTINUITY_WAIVED` label and its doubled weight, profile `register_multiplier`, the
`segment_rate_adders` of `program.ini` and the `dispatch_start` order of the season ledger.

The hidden generators assert every drawn value is inside the stated bounds (at most 3
candidate offers per site in an event, acyclic `draws_from` chains, non-negative amounts); the
season and settlement generators plant a separating grant pool in every region. Hidden, wide
and mutated checks carry 173 of 237 points.

Measured in Docker (tests channel, stub rewardkit, 2 CPU), in points of 237: the oracle
scores 237. An exact portfolio search that visits every portfolio scores 173: it passes every
check except the sixteen wide ones, where each run ends at the 120 s limit. A cheapest-first pick
scores 72. One wrong reading alone, as a patched oracle: survivors routed back through the
claims test 192, one link of `draws_from` 182, relief ticks instead of credited relief 179.

The judge has 11 criteria (+24/-5). R11 is the code-quality criterion. R5 grades exact arithmetic
and R6 a final run on the shipped data. R8, R9 and R10 grade reruns of the program on altered
copies of `/app/data`: one event-region's pool lowered below its beneficiaries' claims (grants
compared with an outside recompute), the allowance a chosen offer's site draws on lowered below
that offer's relief (is the offer still selected) and one event's uplift raised so a chosen
offer's rate is above its cap (`credit_cents` compared with an outside recompute). R1 to R4 grade
runs on extracts the agent builds itself. The self-check stage of `solution/solve.sh` (an inline
Python block run after the program) recomputes grant cents, drawn allowances and credits on the
shipped data and prints whether they agree. Its own-extract stage writes four small extracts in
the schema (a drawn allowance, two events sharing a site whose start times carry different UTC
offsets, an override with uplift and adder above the cap, one chosen offer with two half-cent
interval amounts), runs `/app/out/derive_report.py` on each and prints the program's
`candidate_offer_count`, selecting events, `credit_cents` and `cap_binding_count` beside figures
worked out by hand (1, OWN-0202 only, 40 and 1, 4), then makes the three altered copies under
its temp dir and prints the program's figure beside the recomputed one for each.

## Root cause

The difficulty is reading three rules exactly and carrying them through a season:

- the second grant share is a share of every cent of F, not a second pass through the claims
  test;
- the allowance a site draws on is found by following `draws_from` to a site with a blank
  entry, however many links that takes;
- the credit of an interval is priced on credited relief, a term defined in schema section 6,
  not on the relief ticks reported elsewhere;
- unallocated cents travel to the region's next event, so a slip in one pool moves the rest of
  the region's season.

## Solution shape

1. Read `program.ini`: units, code maps, segment rate adders and the `[grants]` keys.
2. Load every file with the row rules of section 1 (unknown regions, orphans, out-of-range and
   duplicate profile rows; register multipliers; ticks when first derived).
3. Group authorized offers by event-region.
4. Walk events in start-instant order (descending id on equal instants). For each event-region
   keep an offer only if its total relief fits what remains of the allowance its site draws on
   (follow `draws_from` to its end); choose the portfolio exactly; then draw the chosen relief
   from those allowances. The reference treats offers of one site with identical relief,
   recovery and cost as one choice with a multiplicity (the greatest id stands for the group,
   tie counts multiply), tries sites and offers with more relief first and the empty choice
   last, and stops a branch once a lower bound on components 1 and 2 (relief still reachable,
   capped at the ceiling) is already worse than the best portfolio. The wide extracts take it
   under 10 seconds per run in Docker.
5. Credit each chosen offer per interval: credited relief ticks times `wh_per_tick` times
   `min(start + uplift + adder, cap)`, divided by 1000 times `millicents_per_cent`, rounded half
   to even, then summed.
6. In the same season order, per region: F = max(0, pool + carried - credit). Pay claims when
   they fit; else largest remainder, drop shares under the minimum, and share all of F again over
   the survivors by largest remainder. Carry F minus allocated cents to the region's next event.
7. Label site rows, build region and segment entries in event id order, totals, audit and data
   quality, and write sorted-key JSON with a trailing newline.

## Ordered plan

1. Read schema.md and every comment it names; list the conventions of section 2.
2. Inspect sample records of each file and check codes against `program.ini`.
3. Implement loading, the ledger with allowance holders, the exact search, settlement, grants
   with carried cents, and the reports.
4. Build small extracts of your own: a `draws_from` chain of several links, an interval with
   both relief and recovery, a pool where a beneficiary falls under the minimum; recompute the
   expected figures by hand and compare.
5. Run the final program on `/app/data` and report what it does and how it was checked.

## Pitfalls

- Routing the survivors of the minimum drop back through the claims test.
- Keeping the first shares of the survivors instead of sharing every cent of F again.
- Ignoring the minimum grant.
- Reading `draws_from` one link deep, or ignoring it.
- Pricing credits on relief ticks instead of credited relief ticks.
- Funding a pool without the carried cents, or carrying in event id order.
- Sharing the raw pool, or funding it from uncapped or unrounded credits.
- Walking events by `event_id` or by the start string; serving equal instants in ascending id.
- Taking an override as the whole rate, dropping the uplift or adder, or capping first.
- Rounding a credit once per offer, or half up.
- Adding raw Wh before converting to ticks; dropping the register multiplier.
- Comparing overdelivery before cost, or offer count before overdelivery.
- Assuming at most 8 sites per event-region, or visiting tied portfolios one at a time, so a
  wide extract runs past 120 seconds; picking offers cheapest first instead of exactly.
- Reading a blank `waiver_signed` as `Y` from the `[export]` defaults.
- Emitting floats or booleans, unsorted keys, missing keys or no trailing newline.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: district-heat-flex-procurement
task_name: terminal-bench/district-heat-flex-procurement
fix_patch_sha256: b2b8ff3d74aeeb9293d883048d5bf53cf567d448fb9dfe8728f04b2bf11822bb  # sha256 of solution/solve.sh
solve_py_sha256: d5ce561b7611140ac924edc3ba6958d182987cea0273d39138835d837e23083d  # sha256 of solution/solve.py
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
