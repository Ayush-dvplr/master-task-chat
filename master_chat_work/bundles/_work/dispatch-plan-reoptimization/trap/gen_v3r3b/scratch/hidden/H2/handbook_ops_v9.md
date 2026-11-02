# Network Replan Operating Handbook, revision 9

This handbook is the governing contract for the replan cycle. Every rule the
graded work depends on is written out here. Nothing is redacted.

## 1. Scope and discovery

The export set is flat. One source is a database that carries a `sources`
table naming every shipped file with its `role`, its `fmt`, a `record_count`
and an `authority` value. Discover the corpus through that table rather than by
guessing from file names: names are operational codes and do not describe
content. Authority values are `primary`, `mirror`, `superseded`, `contract` and
`informational`. Only `primary` and `contract` sources feed a figure. A `mirror`
or `superseded` source is read for reconciliation counts only, and an
`informational` source is never allowed to supply a coefficient. Operator notes,
audit trails, the previous run report and the `superseded_parameters` and
`retired_aliases` blocks of the contract files carry legacy and indicative
figures that are retained for traceability; every one of them is superseded by
the registers and by the documents the authority table names.

## 2. Planning sequence cutoff

Every register row carries `effective_seq`. The cutoff is the
`plan_sequence_cutoff` in the runbook configuration, cross confirmed by the
`cutoff_control` table of the authority database and by the energy memorandum.
A row whose `effective_seq` is greater than the cutoff is out of scope for the
plan and is never selected, never accumulated and never counted as rejected because of the cutoff; the section 14 rejection reasons are applied first, and a row
that survives them is counted as out of scope.

## 3. Row identity, revision and lifecycle

Each register row carries `row_uid`. A row is live when all of the following
hold: its `effective_seq` is at or below the cutoff, its own `void` field is 0,
and the row lifecycle log does not leave it voided. The lifecycle log is the
`row_lifecycle` source; it carries `seq`, `row_uid` and `action` where `action`
is `void`, `restore` or `note`. For one `row_uid`, take the log entries at or
below the cutoff, order them by `seq`, and let the last `void` or `restore`
decide: a trailing `void` kills the row, a trailing `restore` revives it. The
`row_lifecycle_superseded` source is the retired register of the same kind and
never changes a row state.

Within one logical key the live row with the highest `rev` wins. Ties break on
the highest `effective_seq`, then on the later row in canonical order, where
canonical order is file name ascending and row order inside a file.

Three registers accumulate rather than supersede: the cost amendment register,
the capacity adjustment register and the handling adjustment register. An
accumulating register carries a logical identity column, `amend_id` or `adj_id`,
and rows that repeat one identity are one entry that is added once, taking the first live row in canonical order. Every other
register supersedes.

## 4. Sentinels, codes, scales and currency

The sentinel tokens are listed in the nomenclature contract. A row whose
governing value is a sentinel is rejected, is reported in the rejection
artifact, and never takes part in supersession.

Identifier columns carry clerical noise. Normalise a code by trimming
whitespace, upper casing, deleting `-` and `_`, and zero padding the numeric
tail to two digits. `s3`, `S-03`, ` s_3 ` and `S03` are the same plant.

Scale tokens: `kcents` multiplies by one thousand, `cents` multiplies by one,
`units_dz` holds dozens and multiplies by twelve, a `pct` unit multiplies by one
hundred to reach basis points, and a basis point figure divides by ten thousand.

Amounts marked `EUR` convert to United States cents with the treasury rate whose
`effective_seq` is the highest at or below the cutoff among live rate rows:
`usd_cents = round_half_up(eur_cents * usd_per_eur_micros / 1000000)`.

All money is integer United States cents. Rounding is half up, away from zero,
applied at each conversion named in this handbook and nowhere else.

## 5. Horizon and item scope

The horizon is the period set ordered by `fiscal_ordinal` from the period window
register, whose live winner per period is selected by the rules in section 3.
The period flagged `fy_start` is ordinal one. Report and iterate in that fiscal
order everywhere, never in period code order, except that JSON object keys follow the sorted keys rule of section 14.

An item whose live status in the item status register is `retired` is out of
scope: its demand rows are rejected with reason `retired_item` and it appears in
no plan artifact. An item that appears in a demand register but has no live row
in the item status register, including an item listed there only by rows above
the cutoff, is rejected with reason `unknown_item`. The item status mirror
source is stale and never decides status.

A plant and period pair whose live status is `mothballed` has zero capacity for
that period regardless of the capacity registers.

## 6. Demand rebuild

Demand keys are item and period. Demand rows live in six block registers and in
two overlay registers. All eight are one logical register: supersession by `rev`
runs across the whole set, so an overlay revision can outrank a block revision
for the same key. A block register that dates rows by calendar date resolves the
date to a period through the calendar register.

A demand column named in the dozens alias list is expressed in dozens and is
multiplied by twelve. A missing key means zero demand.

## 7. Coefficient rebuild

For each in scope item and period the unit cost coefficient is built in this
order.

1. Base amount: the live winning row of the unit cost registers, expanded by its
   `scale` token and converted from its `ccy` denomination.
2. Amendments: the amendment register accumulates rather than supersedes. Sum
   every live amendment row for the key, treating `sign` of `credit` as
   negative and `charge` as positive. Rows that repeat the same `amend_id` are
   one amendment and are counted once.
3. Override: if the override register has a live winning row for the key, it
   replaces the accumulated value outright.
4. Energy uplift: add `round_half_up(value * (index_bps + surcharge_bps) /
   10000)`, where `index_bps` is the live winning period index expressed in basis
   points and `surcharge_bps` is the energy surcharge published in the energy
   memorandum. The two figures add before the multiplication.

The setup coefficient is the live winning row of the setup registers, expanded by
its `scale` token. A key with no live setup row takes the `setup_fallback_cents`
that its item carries under `item_defaults` in the runbook. An item that
`item_defaults` does not list takes the control `default_setup_cents`.

The holding coefficient is `round_half_up(unit_cost_cents * holding_rate_bps /
10000)` where `holding_rate_bps` is published only in the penalty schedule
document. Holding is charged per unit of inventory carried from one period to the
next.

Each coefficient carries a flag string built from these letters, sorted
alphabetically and joined with `+`, empty when none apply: `AMD` an amendment was
accumulated, `CUT` at least one row for the key was excluded by the cutoff, `ENR`
the energy uplift was non zero, `FX` the winning base row was denominated in
EUR, `KC` the winning base row used the kcents scale, `OVR` an override replaced
the value, `VOI` at least one row for the key was voided by its own field or by
the lifecycle log. The `CUT` and `VOI` letters read the unit cost register, the
amendment register and the override register for that key and nothing else.

## 8. Capacity and handling rebuild

Capacity for a plant and period is
`round_half_up(round_half_up((base + adjustments) * shift_bps / 10000) *
derate_bps / 10000)`, floored at zero, and zero when the pair is mothballed.
`base` is the live winning capacity base row, `adjustments` is the sum of live
adjustment rows for the pair, `shift_bps` is the live winning shift pattern of
the plant and `derate_bps` is the live winning holiday derate of the period.

Handling for a plant and period is
`round_half_up((base + adjustments) * (10000 + zone_uplift_bps) / 10000)` where
the zone is the live winning zone of the plant and `zone_uplift_bps` is the live
winning uplift of that zone. Selected capital projects then reduce the plant
handling rate by the sum of their unit savings, floored at the runbook minimum
handling rate.

## 9. Stage one of the plan, capital selection

Capital projects are registered in the project register; their capital cost, unit
saving and eligibility ruling live in three further registers, and their
committed business case volume lives in the capital programme workbook. Apply
sections 3 and 4 to each of those registers.

A project is a candidate when its live eligibility ruling is `yes`. The value of
a candidate is `unit_saving_cents * committed_volume_units`. Select the candidate
set that maximises total value subject to total capital cost at or below the
funded envelope published in the capital programme workbook. Capital costs and
the envelope are exact multiples of the runbook capital grid.

Ties resolve in this order: highest total value, then lowest total capital cost,
then the smallest indicator, where the indicator reads the candidate list in
ascending project code with the first project as the least significant bit, so a
tie prefers dropping the later project.

The steering figure quoted in the operator notes is not the funded envelope.

## 10. Stage two of the plan, lot sizing

For each in scope item, choose production quantities over the fiscal horizon that
meet every period demand with no backlog and minimise setup, production and
holding cost. Production in a period covers a contiguous block of periods
starting at that period. Carrying one unit from a period to the next costs the
holding coefficient of the period it is carried out of.

The cost of covering the block that starts at period `a` and ends before period
`b` by producing at `a` is the setup coefficient at `a`, plus the unit cost at
`a` times the block demand, plus the holding charge accrued while the later
demand waits. A block whose demand is zero opens no production and carries no
setup charge. When two schedules cost the same, compare their production periods
starting from the last one in fiscal order and moving back; at the first position
where they differ, the schedule whose production period there is earlier in
fiscal order wins.

## 11. Stage three of the plan, sourcing

For each period the required quantity is the total produced across items in that
period. Plants receive units cheapest first by handling rate, ties broken by the
lower plant code, each up to its capacity. Units that no plant can take are the
period shortfall and are charged the shortfall penalty per unit published in the
penalty schedule document. Within a plant the received units are drawn from items
in ascending item code order.

## 12. Objective

The corrected objective is the sum of production cost, setup cost, holding cost,
handling cost, shortfall penalty and the capital cost of the selected projects.
Production cost is the unit coefficient times the produced quantity. Handling
cost is the post selection plant rate times the units the plant received.

## 13. Certificates and sensitivity

The optimality certificate reports four checks. The capital check confirms that
no unfunded candidate with a positive value fits in the remaining envelope. The
lot sizing check confirms the zero inventory property, that production only
starts in a period whose entering inventory is zero, and that the reconstructed
schedule cost equals the programme cost. The sourcing check confirms that no
plant with idle capacity carries a rate below a plant that received units in the
same period. The coverage check confirms that every demanded unit is either
produced or charged as shortfall.

The sensitivity report prices one more grid unit of envelope as the optimal
capital value at envelope plus one grid unit minus the optimal value at the
envelope. It also prices one more produced unit in each period as the handling
rate of the cheapest plant with idle capacity in that period, or the shortfall
penalty when no plant has idle capacity. The envelope is binding when that
marginal value is above zero.

## 14. Output contract

Every JSON artifact is written with sorted keys, one space of indentation and a
trailing newline. Every JSONL artifact is one compact object per line with sorted
keys and no spaces after separators. Every CSV artifact carries the header named
below, uses comma separators, and ends with a newline. All files use line feed
endings and UTF-8.

`corrected_coefficients.jsonl` carries one object per in scope item and period
ordered by item code then fiscal ordinal, with keys `demand_units`,
`energy_bps_applied`, `fiscal_ordinal`, `flags`, `holding_cost_cents`, `item`,
`period`, `setup_cost_cents`, `unit_cost_cents`.

`objective.json` carries `capex_cents`, `handling_cost_cents`,
`holding_cost_cents`, `items_in_scope`, `periods_in_horizon`, `plants_in_scope`,
`production_cost_cents`, `setup_cost_cents`, `shortfall_penalty_cents`,
`total_demand_units`, `total_objective_cents`, `total_produced_units`,
`total_shortfall_units`.

`optimal_plan.jsonl` carries one object per opened production period ordered by
item code then fiscal ordinal, with keys `covers_periods`, `fiscal_ordinal`,
`item`, `period`, `production_cost_cents`, `produced_units`, `setup_cost_cents`.
`covers_periods` lists the periods of the covered block that carry demand, in
fiscal order.

`production_schedule.csv` carries
`item,period,fiscal_ordinal,demand_units,produced_units,ending_inventory_units`
for every in scope item and period, ordered by item code then fiscal ordinal.

`holding_profile.csv` carries
`item,period,fiscal_ordinal,ending_inventory_units,holding_rate_cents,period_holding_cents,cumulative_holding_cents`
in the same order.

`sourcing_allocation.csv` carries
`period,fiscal_ordinal,plant,item,units,handling_rate_cents,handling_cost_cents`
for every assignment of at least one unit, ordered by fiscal ordinal, then plant
fill order, then item code.

`plant_utilization.csv` carries
`plant,period,fiscal_ordinal,capacity_units,assigned_units,idle_units,utilisation_bps`
for every plant and period, ordered by plant code then fiscal ordinal.
`utilisation_bps` is `round_half_up(assigned * 10000 / capacity)` and is zero when
capacity is zero.

`shortfall_ledger.csv` carries
`period,fiscal_ordinal,required_units,capacity_units,shortfall_units,penalty_rate_cents,penalty_cents`
for every period in fiscal order.

`retrofit_selection.json` carries `budget_cents`, `candidate_project_ids`,
`capex_grid_cents`, `eligible_project_count`, `rejected_project_ids`,
`selected_capex_cents`, `selected_project_ids`, `selected_value_cents`; `rejected_project_ids` lists the candidates left unfunded, and every list of project codes, here and in `incumbent_delta.json`, is in ascending project code.

`budget_utilization.json` carries `budget_binding`, `budget_cents`,
`capex_cents`, `slack_cents`, `slack_grid_units`, `utilisation_bps`.
`slack_grid_units` divides the slack by the grid and drops any remainder, and
`utilisation_bps` is `round_half_up(capex * 10000 / envelope)`.

`period_costs.json` is keyed by period code, each value carrying
`handling_cost_cents`, `holding_cost_cents`, `production_cost_cents`,
`setup_cost_cents`, `shortfall_penalty_cents`, `total_cents`. Capital cost sits
outside the period breakdown.

`item_summary.json` is keyed by item code, each value carrying `demand_units`,
`family`, `holding_cost_cents`, `produced_units`, `production_cost_cents`,
`setup_count`, `setup_cost_cents`, `total_cents`, where `total_cents` adds
production, setup and holding only.

`binding_constraints.json` carries `binding_count`, `budget_binding`,
`full_capacity_plant_periods`, `shortfall_periods`, `zero_capacity_plant_periods`,
where each plant and period entry is a two element list of codes, the two plant and period lists are ordered by plant code then fiscal ordinal, and `binding_count` is the number of full capacity plant periods plus the number of shortfall periods plus one when the envelope is binding.

`optimality_certificate.json` carries `all_demand_covered_or_charged`,
`capital_no_unfunded_candidate_fits`, `lot_sizing_reconstructed_cost_matches`,
`lot_sizing_zero_inventory_property`, `sourcing_no_cheaper_idle_capacity`,
`total_objective_cents`. Each of the five check keys, and `budget_binding` in every artifact that carries it, holds a JSON boolean: `true` when the condition holds and `false` otherwise.

`incumbent_delta.json` carries `component_deltas`, `corrected_selected_project_ids`,
`corrected_total_objective_cents`, `delta_cents`, `incumbent_selected_project_ids`,
`incumbent_total_objective_cents`, `projects_added`, `projects_dropped`, where
`component_deltas` is keyed by the objective component names of `objective.json`
that both runs publish. Every delta, `delta_cents` and each component delta
included, is the corrected figure minus the incumbent figure.

`coefficient_corrections.csv` carries
`item,period,incumbent_unit_cost_cents,corrected_unit_cost_cents,delta_cents,flags`
for every in scope key whose corrected coefficient differs from the coefficient
the previous run published, ordered by item code then fiscal ordinal.

`sensitivity_report.json` carries `budget_binding`, `budget_grid_unit_cents`,
`marginal_value_of_one_grid_unit_cents`, `next_unit_cost_by_period`,
`top_unfunded_capex_cents`, `top_unfunded_project_id`, where
`next_unit_cost_by_period` is keyed by period code. The top unfunded candidate
is the one with the highest value to capital ratio among candidates left out,
ties broken by the lower project code, and the fields are the empty string and
zero when every candidate is funded.

`data_quality.json` carries `count_mismatches`, `sources` and `totals`. `sources`
is a list ordered by source name, each entry carrying `authority`, `fmt`, `name`,
`record_count_declared`, `role`, `rows_seen`. `count_mismatches` lists the names
whose physical row count differs from the declared count, ordered by name. A
declared count that differs from the physical count is a stale count column: the
physical count governs everywhere and only the name is reported.

The rejection and accounting sweep runs once over every `primary` source held in
a delimited, line delimited, JSON, XML or plain text format, in manifest name
order, and visits each row once. A demand row whose item has no live row in the
item status register is rejected as `unknown_item`; a demand row whose item is retired
is rejected as `retired_item`; any other row that holds a sentinel token in any
field is rejected as `sentinel`. The first reason in that order is reported.
`totals.rejected_rows` is the row count of the rejection artifact.
`totals.out_of_scope_rows` counts sweep rows that survive rejection, carry an
`effective_seq`, and sit above the cutoff. `totals.void_rows` counts sweep rows
that survive rejection, carry an `effective_seq` at or below the cutoff, and are
blocked by their own `void` field or by the lifecycle log.
`totals.sources_seen` is the number of manifest entries.

Physical row counting is defined per format. Delimited registers count data lines
after the header. Line delimited JSON registers count non empty lines. A JSON
register counts the entries of its records array. An XML register counts the
child elements of its root. A text register counts non empty lines that do not
start with `#`. A markdown or configuration register counts non empty lines that
do not start with `#`. A database counts the sum of rows over its user tables. A
workbook counts data rows after the header row of every sheet. The schedule
document and the memorandum count the lines that begin with the record prefix
`R|`.

`rejected_records.csv` carries `source,row_uid,key,reason` for every rejected row,
ordered by source name then `row_uid`. Reasons are `retired_item`, `sentinel` and
`unknown_item`. The `key` column joins the identifiers the row carries in the
order item, period, plant, project, zone, separated by a colon, where a dated
demand row resolves its period through the calendar. Every identifier column the row carries is joined, a sentinel included, after the code normalisation of section 4, so one that normalises to nothing leaves its field empty.

`reconciliation.txt` carries one `key=value` line per figure in this order:
`corrected_total_objective_cents`, `incumbent_total_objective_cents`,
`delta_cents`, `selected_capex_cents`, `budget_cents`, `total_shortfall_units`,
`shortfall_penalty_cents`, `items_in_scope`, `rejected_rows`.

`audit_summary.md` opens with the heading `# Replan Audit Summary` and a blank
line, then one `- key: value` bullet per figure in the same order and with the
same names as the reconciliation file, then a blank line, then the line
`Selected projects: ` followed by the selected project codes joined with `, `.

## 15. Worked micro examples

A cost row `amount=3, ccy=EUR, scale=kcents` at a cutoff rate of `1074000`
micros expands to `3000` EUR cents and converts to
`round_half_up(3000 * 1074000 / 1000000) = 3222` United States cents.

A demand row `units_dz=41` is `492` units.

An index row `index_value=2, unit=pct` is `200` basis points; with a surcharge of
`214` basis points a coefficient of `4000` gains
`round_half_up(4000 * 414 / 10000) = 166` cents.

A capacity pair with base `1800`, adjustments `-120`, shift `9500` and derate
`8800` is `round_half_up(round_half_up(1680 * 9500 / 10000) * 8800 / 10000) =
round_half_up(1596 * 8800 / 10000) = 1404` units.

A key whose winning row was revived by a `restore` entry after a `void` entry
carries the `VOI` flag even though the row is live.
