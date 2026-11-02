# District heat flexibility programme: data contract

This file is the rulebook for one season extract of the winter demand-response
programme. Every figure in every report is defined here or in the comment lines of
the data file this file names for it; a comment that states how a file's own fields
are read is binding. Where a section says a choice "follows the programme
conventions", the rule is in section 2 and it is binding there exactly as if it were
repeated.

## 1. Files and keys

All files sit flat in the data directory. Text is UTF-8. CSV files are comma
separated and TSV files are tab separated; both start with one header row, and the
records below it are the data rows. Identifiers are compared exactly as written.
Row order inside any file carries no meaning unless its description below says
otherwise.

- `program.ini` (read with Python `configparser`).
  - `[units]`: `wh_per_tick` (Wh in one energy tick) and `millicents_per_cent`.
  - `[region_codes]`: each option is a feeder code and its value is the region name
    the code belongs to. Several codes can name the same region.
  - `[segment_codes]`: each option is a segment code and its value is the segment name.
  - `[segment_rate_adders]`: each option is a segment name and its value is an integer
    in mill-cents per kWh; the comment above the section says how it applies. A segment
    name with no option has an adder of 0.
  - Codes in the other files are written in upper case. Option names in this file
    are matched without regard to letter case, which is how `configparser` reads them.
  - `[export]` belongs to the export tool that wrote the file and carries no rule for
    this programme.
  - Every `region_code` in every file (`sites.csv`, `targets.tsv`, `feeder_limits.txt`,
    `segment_floors.json` and `pools.txt`) stands for its region name through
    `[region_codes]`, and records are always matched on the region name, never on the
    code. Segment codes likewise go through `[segment_codes]`.
- `events.json`: a JSON array with one object per event: `event_id`, `name`
  (informational), `interval_count`, `objective` (an object with the integers
  `cost_weight` and `recovery_weight`), `dispatch_start` (the instant the event starts,
  an ISO 8601 date and time with its UTC offset) and `uplift_millicents_per_kwh`, which
  is added to the rate of every site row of the event. Intervals of an event are numbered
  1 to `interval_count`. Every `event_id` used by another file appears here.
- `sites.csv`: columns `event_id`, `site_id`, `region_code`, `segment_code`,
  `beneficiary_id`, `critical`. One row per site taking part in an event (a "site
  row"). The pair (`event_id`, `site_id`) is unique. `critical` is `Y` or `N`. The
  site's region is the region name of its `region_code`, and its segment is the
  segment name of its `segment_code`. A row whose `region_code` is not an option of
  `[region_codes]` has an unknown region: it is skipped and counted, it is not a site row
  for any purpose, and the lines of `site_state.jsonl`, `continuity_waivers.csv`,
  `rate_cards.xml` and `recipient_weights.tsv` for its `event_id` and `site_id` are
  skipped. Region codes in the other files are always options of `[region_codes]`.
- `offers.csv`: columns `offer_id`, `event_id`, `site_id`, `mode_label`,
  `bid_cost_cents`. Each offer is one operating mode of a site in an event.
  `mode_label` is informational. An offer whose (`event_id`, `site_id`) has no site row
  is an orphan offer: it is skipped and counted.
- `profiles.tsv`: columns `offer_id`, `interval`, `relief_wh`, `recovery_wh`,
  `register_multiplier`. `relief_wh` and `recovery_wh` are meter register readings and
  `register_multiplier` is a positive integer: the row's relief in Wh is its `relief_wh`
  times its `register_multiplier`, and its recovery in Wh is its `recovery_wh` times its
  `register_multiplier`. An interval with no kept row means 0 Wh of both. Rows are read
  in file order, and each row takes the first of these kinds that applies to it:
  1. its `offer_id` does not appear in `offers.csv`: an orphan profile row;
  2. its `interval` is outside 1 to the `interval_count` of the event of its offer's
     `offers.csv` row: an out-of-range profile row;
  3. an earlier row with the same `offer_id` and `interval` was kept: a duplicate
     profile row.

  Rows of these three kinds are skipped and counted; every other row is kept.
- `targets.tsv`: columns `event_id`, `region_code`, `interval`, `target_wh`,
  `shortfall_weight`. Exactly one row per event, region and interval; `region_code`
  may be any code of that region.
- `feeder_limits.txt`: fixed-width text. Lines starting with `#` are comments. In
  every other line, character columns 1-10 hold `event_id` (left aligned, space
  padded), 11-14 `region_code` (left aligned), 15-17 `interval`, 18-27
  `relief_ceiling_wh` and 28-37 `recovery_ceiling_wh` (right aligned). Exactly one line
  per event, region and interval.
- `site_state.jsonl`: one JSON object per line with `event_id`, `site_id` and the JSON
  booleans `dispatch_authorized`, `safety_hold` and `cooldown`. One line per site row.
- `continuity_waivers.csv`: columns `event_id`, `site_id`,
  `routine_certificate_pending`, `waiver_status`, `waiver_signed`. One row per site row.
  `routine_certificate_pending` is `Y` or `N`. `waiver_status` is one of `VALID`,
  `EXPIRED`, `REVOKED`, `NONE`. `waiver_signed` is optional: `Y`, `N`, or empty when the
  field was not recorded.
- `segment_floors.json`: an object whose `floors` key holds an array of objects with
  `event_id`, `region_code`, `segment_code`, `floor_wh` and `priority_weight`. At most
  one entry per event, region and segment. A missing entry means a floor of 0 with a
  priority weight of 0.
- `rate_cards.xml`: root element `rate_cards`; one `card` element per site row, with
  attributes `event` and `site` and child elements `base` and `cap`, and on some cards
  an `override` element, all integers in mill-cents per kWh. The comment at the top of
  the file says how a card's rate and an offer's credit are formed.
- `recipient_weights.tsv`: columns `event_id`, `site_id`, `grant_weight`. At most one
  row per site row. A site row with no weight row is not a grant recipient.
- `pools.txt`: fixed-width text. Lines starting with `#` are comments. In every other
  line, character columns 1-10 hold `event_id`, 11-14 `region_code` and 15-26
  `pool_cents` (right aligned). At most one line per event and region; a missing line
  means a pool of 0.
- `site_allowances.tsv`: tab separated. Lines starting with `#` are comments; the first
  other line is the header `site_id`, `allowance_ticks`, and every line after it is a
  data row, one per `site_id` of `sites.csv`. The comment at the top of the file says how
  an allowance is drawn.
- `export_manifest.tsv`: tab separated. Lines starting with `#` are comments and say
  what the file records; the first other line is the header `file`, `records`,
  `field`, `field_sum`, and every line after it is a data row. No report figure is
  taken from it.

An event-region is one event from `events.json` together with one region name from
`[region_codes]`. Every event has every region, including regions where the event has
no site rows.

## 2. Programme conventions

### 2.1 Units

Energy in every report is counted in ticks; one tick is `wh_per_tick` Wh. Money is
integer cents. Rates are mill-cents per kWh: `millicents_per_cent` mill-cents make one
cent and 1 kWh is 1000 Wh. Ratios are integer basis points, where 10000 is 100 percent.

### 2.2 Rounding

"Rounded half up" means rounded to the nearest integer, with an exact half going up.
"Rounded half to even" means rounded to the nearest integer, with an exact half going to
the even neighbour.
Every figure in this contract is non-negative. Compute with exact integer or rational
arithmetic; binary floating point is never used for a reported figure.

### 2.3 Quantise when first derived

Every Wh value of a record becomes ticks (the Wh value divided by `wh_per_tick`,
rounded half up) at the moment it is derived from that record, and every energy sum is
a sum of such ticks.

### 2.4 Ordered choice among equals

Whenever an ordered choice is needed among candidates that are equal on every stated
criterion, the greatest identifier wins. Identifiers compare as plain strings in code
point order. A set of identifiers compares as the tuple of its members sorted
ascending, using Python tuple order. When equal candidates receive something one at a
time, they are served in descending identifier order.

### 2.5 Caps

A cap always binds the final rate, after every adjustment to that rate has been
applied.

### 2.6 Compliance findings

Every site row gets exactly one compliance label: the highest-ranked finding that
applies, in this ranking from highest to lowest: `SAFETY_HOLD`, `COOLDOWN`,
`CONTINUITY_WAIVED`, `CERTIFICATE_PENDING`, `CLEAR`. A continuity waiver is valid only
when all four of these hold: `waiver_status` is `VALID`, `waiver_signed` is `Y`, the
site row is critical, and the site's segment is `public`. `CONTINUITY_WAIVED` applies to
a site row whose routine certificate is pending and whose continuity waiver is valid.

## 3. Eligibility

A site row can dispatch only when its `site_state.jsonl` line has
`dispatch_authorized` true. The candidate offers of an event-region are the offers,
orphans excluded, whose site row belongs to that event-region and can dispatch, less
the offers that the comment at the top of `site_allowances.tsv` excludes. Compliance
labels never change eligibility.

An event-region has at most 8 sites with candidate offers and at most 3 candidate
offers per site. Each run of the program on an extract must finish within 120 seconds.

## 4. Compliance

`SAFETY_HOLD` applies when `safety_hold` is true, `COOLDOWN` when `cooldown` is true,
`CERTIFICATE_PENDING` when `routine_certificate_pending` is `Y`, and `CLEAR` always
applies. `CONTINUITY_WAIVED` is defined in 2.6. The label a site row receives is chosen
by the programme conventions.

## 5. Optimisation

For each event-region choose one portfolio: a set of candidate offers holding at most
one offer per site. Choosing no offer at a site is allowed, and so is the empty
portfolio.

For a portfolio and interval t, relief(t) is the sum of the relief ticks of its offers
at t and recovery(t) the sum of their recovery ticks. The portfolio is feasible when,
in every interval, relief(t) is at most the relief ceiling in ticks and recovery(t) is
at most the recovery ceiling in ticks.

Among feasible portfolios the best one is chosen by these components, each smaller is
better, compared in this order; a later component only matters when all earlier ones
are equal:

1. weighted shortfall: the sum over intervals of `shortfall_weight` times
   max(0, target ticks minus relief(t));
2. weighted floor deficit: the sum over the segment names in `[segment_codes]` of the
   floor's `priority_weight` times max(0, floor ticks minus segment relief), where
   segment relief is the relief ticks of the portfolio's offers at that segment's
   sites, summed over all intervals;
3. blended cost: `cost_weight` times the sum of the portfolio's `bid_cost_cents`, plus
   `recovery_weight` times the sum over intervals of recovery(t);
4. overdelivery: the sum over intervals of max(0, relief(t) minus target ticks);
5. the number of offers in the portfolio.

Remaining ties follow the programme conventions.

## 6. Settlement

Every offer in the chosen portfolio earns a performance credit, `credit_cents`, for its
site row; the comment at the top of `rate_cards.xml` defines it. Credits are separate
from bid costs and from grants.

A chosen offer is cap binding when its site row's rate, before its card's cap is
applied, is greater than that cap.

## 7. Grants

Each event-region has a grant pool from `pools.txt`. The calculation order for an
event-region is: the portfolio (section 5), then its credits (section 6), then the funded
pool, then the apportionment below. The funded pool F is the grant pool minus the
event-region's credit cents (the sum of the credits of its chosen offers), or 0 when that
difference is negative.

The recipients are the site rows of the event-region that have a `recipient_weights.tsv`
row. A recipient site row weighs its `grant_weight`, counted twice when the site row's
compliance label is `CONTINUITY_WAIVED`. A beneficiary's weight is the sum of the weights
of its recipient site rows, and W is the sum of all beneficiary weights in the
event-region.

When there are no recipients, the whole funded pool is unallocated. For every other
event-region F is shared by largest remainder: every beneficiary with a positive weight
w first gets floor(F times w / W) cents, and its remainder is (F times w) mod W. The cents left over
are handed out one cent at a time to beneficiaries in decreasing order of remainder;
equal remainders follow the programme conventions. The allocated cents are the sum
handed to beneficiaries, and the unallocated cents are F minus the allocated cents.
Beneficiaries with weight 0 receive nothing and are not listed.

The residual cents of a pool are the cents of its funded pool handed out by remainder. A
pool has a residual tie when two or more of its beneficiaries with positive weight share
the same non-zero remainder.

## 8. Outputs

`python3 derive_report.py DATA_DIR OUT_DIR` reads an extract from `DATA_DIR`, creates
`OUT_DIR` when it is missing, and writes the nine JSON files below into it. Every JSON
file holds one object, is written with sorted keys at every level and ends with a
newline. Every number is a JSON integer: no floats and no booleans anywhere.
Indentation is free. Region and segment names are the names from `program.ini`.

### 8.1 `region_<region>.json`

One file per region name, for example `region_North.json`. Keys:

- `region`: the region name.
- `events`: one entry per event in `events.json`, ascending by `event_id`, each with:
  - `event_id`
  - `candidate_offer_count`: candidate offers of the event-region
  - `selected_offer_ids`: the chosen portfolio's offer ids, ascending
  - `intervals`: one entry per interval, ascending, each with `interval`,
    `target_ticks`, `relief_ticks`, `recovery_ticks`, `shortfall_ticks`
    (max(0, target minus relief)) and `overdelivery_ticks` (max(0, relief minus target))
  - `bid_cost_cents`: the sum of the chosen offers' bid costs
  - `credit_cents`: the sum of the chosen offers' credits
  - `grant_pool_cents` (the `pools.txt` pool), `grant_funded_cents` (F),
    `grant_allocated_cents`, `grant_unallocated_cents`
  - `grants`: `{beneficiary_id, cents}` objects for beneficiaries with positive weight,
    ascending by `beneficiary_id`; empty when the pool is unallocated
  - `compliance_counts`: an object with all five labels as keys, counting the site rows
    of the event-region
- `totals`: `event_count`, `candidate_offer_count`, `selected_offer_count`,
  `relief_ticks`, `recovery_ticks`, `shortfall_ticks`, `overdelivery_ticks`,
  `bid_cost_cents`, `credit_cents`, `grant_pool_cents`, `grant_funded_cents`,
  `grant_allocated_cents` and `grant_unallocated_cents`, each summed over the region's
  `events` entries (energy
  summed over all intervals).

### 8.2 `segment_<segment>.json`

One file per segment name, for example `segment_public.json`. Keys:

- `segment`: the segment name.
- `event_regions`: one entry per event-region, ascending by `event_id` and then by
  region name, each with `event_id`, `region`, `selected_offer_ids` (the chosen offers
  at this segment's sites, ascending), `relief_ticks` and `recovery_ticks` (those offers,
  summed over all intervals), `bid_cost_cents`, `credit_cents`, `floor_ticks` and
  `floor_attainment_bp`.
- `floor_attainment_bp` is 10000 when `floor_ticks` is 0, and otherwise the smaller of
  10000 and 10000 times `relief_ticks` divided by `floor_ticks`, rounded half up.
- `totals`: `selected_offer_count`, `relief_ticks`, `recovery_ticks`, `bid_cost_cents`,
  `credit_cents` and `floor_ticks`, summed over `event_regions`.

### 8.3 `summary.json`

Keys: `event_count`, `event_region_count`, `site_count` (site rows),
`candidate_offer_count`, `selected_offer_count`, `relief_ticks`, `recovery_ticks`,
`shortfall_ticks`, `overdelivery_ticks`, `bid_cost_cents`, `credit_cents`,
`grant_pool_cents`, `grant_funded_cents`, `grant_allocated_cents`,
`grant_unallocated_cents`, `regions` and
`segments`. All but the last two are totals over every event-region. `regions` maps every
region name to an object with `selected_offer_count`, `relief_ticks`, `bid_cost_cents`,
`credit_cents` and `grant_allocated_cents`, and `segments` maps every segment name to an
object with `selected_offer_count`, `relief_ticks`, `bid_cost_cents` and `credit_cents`.
The global totals equal the sums over the region files and over the segment files.

### 8.4 `policy_audit.json`

Keys:

- `compliance_counts`: all five labels as keys, counting every site row.
- `site_labels`: `{event_id, site_id, label}` for every site row, ascending by
  `event_id` and then `site_id`.
- `tie_decisions`: one `{event_id, region, tied_portfolio_count, selected_offer_ids}`
  entry for every event-region where two or more feasible portfolios are equal on
  components 1 to 5 at the best value, ascending by `event_id` and then region name;
  `tied_portfolio_count` counts those portfolios.
- `cap_binding_count`: the number of chosen offers that are cap binding.
- `residual_cents`: the residual cents summed over all pools.
- `residual_tie_pool_count`: the number of event-regions whose pool has a residual tie.

### 8.5 `data_quality.json`

Keys are listed in section 9.

## 9. Data quality

`data_quality.json` carries:

- `rows`: an object mapping each of these file names to its record count: `events.json`
  (array entries), `sites.csv`, `offers.csv`, `profiles.tsv`, `targets.tsv`,
  `continuity_waivers.csv`, `recipient_weights.tsv` and `site_allowances.tsv` (data
  rows), `feeder_limits.txt` and `pools.txt` (non-comment lines), `site_state.jsonl` (lines),
  `segment_floors.json` (entries of `floors`), `rate_cards.xml` (`card` elements) and
  `export_manifest.tsv` (data rows).
- `orphan_offer_rows`: orphan offers.
- `orphan_profile_rows`: orphan profile rows.
- `out_of_range_profile_rows`: out-of-range profile rows.
- `duplicate_profile_rows`: duplicate profile rows.
- `unknown_region_site_rows`: `sites.csv` rows with an unknown region.
- `waiver_signed_missing`: data rows of `continuity_waivers.csv` with an empty
  `waiver_signed`.
- `ineligible_offer_count`: offers, orphans excluded, whose site row cannot dispatch.
- `allowance_blocked_offer_count`: offers, orphans excluded, whose site row can dispatch
  but which are not candidate offers because of their site's allowance.
- `empty_candidate_groups`: event-regions with no candidate offer.
- `zero_floor_count`: event-region and segment combinations whose floor is 0, missing
  entries included (a zero denominator for floor attainment).
- `unallocated_pool_count`: event-regions whose funded pool is unallocated: those with no
  recipients and those whose W is 0 (a zero denominator for grants).
