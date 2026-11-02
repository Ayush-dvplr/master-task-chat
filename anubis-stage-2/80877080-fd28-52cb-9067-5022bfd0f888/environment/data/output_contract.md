# Output contract for the corrected plan

The corrected run writes the files below into one output directory. Names are exact.
Rules referenced as P-something are in `cache_planning_rulebook.md`.

General rules:

- Text files are UTF-8 with `\n` line endings and end with a newline. A JSON Lines
  file with no objects is empty (zero bytes).
- JSON files hold one document with sorted keys. JSON Lines files hold one object per
  line with sorted keys.
- Delimited files carry the header shown and no quoting beyond what the delimiter
  forces.
- Nodes, counts, hours, cents, memory units and hop counts are integers. Units,
  unit-hours, GiB, rates and exact savings are plain decimal strings with trailing
  zeros removed and no exponent (`144`, `17.1`, `0.25`, `-3.5`, `0`). Rates are written
  exactly as the bulletin prints the rate in force (four decimals). Percentages have
  exactly two decimals.
- Times are `YYYY-MM-DDTHH:MM:SSZ` in UTC. Ids follow P1.

## cache_plan.csv

Header `pool_id,family,cluster,nodes,cache_units,mem_units,hourly_node_cents,saving_cents,served_pct,utilization_pct`.
One row per candidate pool (P12), sorted by pool_id, including pools planned at 0
nodes, and including the pools of closed clusters (P13A) at 0 nodes. `mem_units` is
P12.7. `hourly_node_cents` is cache units x the effective node rate of P12.5 (the
discounted rate after its rounding when the tier applies).

## pool_curves.psv

Header `pool_id|nodes|cache_units|served_unit_hours|saving_exact_cents`. One row per
candidate pool and allowed node count (P12.3), sorted by pool_id then nodes.
`saving_exact_cents` is the exact saving of P12.6.

## pool_hourly.tsv

Header `pool_id	hour_index	hour_start_utc	usage_units	load_units` (tab separated).
One row per pool (P8, candidate or not) and valid hour, sorted by pool_id then
hour_index. `load_units` is the planning load of P10.

## hourly_rollup.tsv

Header `hour_index	hour_start_utc	pools_valid	load_units	cache_units	served_units	overflow_units`.
One row per lookback hour 0 to H - 1. Over the candidate pools for which the hour is
valid: their count, the sum of their planning load, of their cache units, of
`min(load, cache)` and of `max(0, load - cache)`.

## rates_used.csv

Header `pool_id,family,cluster,scan_rate_cents,node_rate_cents,node_units,min_nodes,growth_pct,tier_units,tier_discount_pct,mem_units_per_node,netted_units,valid_hours`.
One row per pool (P8), sorted by pool_id. The two rates are the rates in force after
Table E-1 (P11), before any tier discount.

## ruleset_used.json

Keys `sheet` (the sheet in force, P11.4), `adoption_id` (its adoption row),
`effective_date` (that row's date, `YYYY-MM-DD`), `node_cap_total`,
`mem_budget_units`, `saving_rounding` and `families`:
a list sorted by upper-case family code of objects with keys `family`, `eligible`
(boolean), `node_units`, `min_nodes`, `family_cap`, `growth_pct`, `tier_units`,
`tier_discount_pct`, `mem_units_per_node`, one per `FAM` row of the sheet in force.

## dedup_report.json

Keys `rows_read`, `duplicate_rows_dropped`, `voided_rows`, `live_queries` (P3, before
adjustments).

## source_lineage.json

Object keyed by shard file name with `rows` (data rows read) and `kept` (P3.3), for
every listed shard.

## applied_adjustments.jsonl

One object per posted journal entry in the order applied: keys `journal` (`jsonl` or
`xml`), `query_id`, `op`, `outcome`, `seq`.

## project_resolution.csv

Header `alias,canonical,hops`. One row per `from_project` of the ledger, sorted by
alias, with the project it resolves to and its hop count as of `W1` (P1.4, P1.5).

## scope_projects.csv

Header `project_id,team,project_status,scope`. One row per registered project (P6
precedence) whose org is the profile's org, sorted by project_id. `scope` is
`IN_SCOPE`, `CLOSED` or `DEV`.

## excluded_queries.jsonl

One object per excluded in-window live query (P7): keys `query_id`, `reason`. Sorted
by query_id.

## reservation_dispositions.csv

Header `reservation_id,pool_id,owner_project,units,effective_end_utc,status`. One row
per reservation (P9), sorted by reservation_id.

## excluded_pools.jsonl

One object per pool excluded by P12.2: keys `pool_id`, `reason`. Sorted by pool_id.

## cluster_commitments.jsonl

One object per closing round of P13A, in round order: keys `round` (1 for the first
closing), `cluster` (the closed cluster), `planned_nodes` (its nodes in the plan that
closed it), `min_nodes` (its Table M-1 commitment), `saving_exact_cents` (the sum of
the exact savings of its pools in that plan, a decimal string) and `short_clusters`
(how many clusters were short in that plan). Empty when no cluster is closed.

## family_rollup.json

Object keyed by upper-case family code for every family with a candidate pool. Each
value has `pools` (candidate pools), `nodes`, `family_cap`, `mem_units` and
`saving_cents`.

## cluster_rollup.xml

```
<clusters plan="PLAN_ID">
<cluster code="..." pools="..." nodes="..." cache_units="..." mem_units="..." saving_cents="..."/>
</clusters>
```

One `cluster` element per cluster with a candidate pool, sorted by code, over its
candidate pools.

## chargeback.csv

Header `pool_id,project_id,team,usage_units,allocated_cents`. One row per pool with
at least one node and project with usage in it (P15), sorted by pool_id then
project_id. `team` is the team of the project's registry row (P6 precedence).

## team_rollup.json

Object keyed by team for every team in `chargeback.csv`. Each value has `projects`
(distinct projects) and `allocated_cents`.

## plan_summary.json

Keys `plan_id`, `ruleset_version`, `lookback_hours`, `out_of_window_queries`,
`excluded_queries`, `candidate_pools`, `selected_pools` (candidate pools with at least
one node), `nodes_total`, `node_cap_total`, `mem_units_total`, `mem_budget_units`,
`total_saving_cents` (P14.2), `chargeback_total_cents` (sum of `allocated_cents`),
`netted_units_total` (sum of netted units over the `NETTED` reservations, a decimal
string) and `closure_rounds` (the number of P13A rounds). `ruleset_version` is the
sheet in force.

## variance_vs_published.csv

Header `pool_id,published_nodes,corrected_nodes,node_delta,published_saving_cents,corrected_saving_cents,status`.
One row per pool in the published plan or among the candidate pools, sorted by
pool_id. Missing sides are empty and count as 0 in `node_delta`. `status` is `NEW`
(not published), `DROPPED` (published but not a candidate pool), `MATCH` (same node
count) or `CHANGED`.

## reconciliation.md

```
# Plan PLAN_ID cache reconciliation

| family | published_nodes | corrected_nodes | delta_nodes |
|---|---|---|---|
| FAMILY | ... | ... | ... |
| ALL | ... | ... | ... |
```

One row per upper-case family code present on either side, sorted, then the `ALL`
row.

## manifest.json

`{"files": [...]}` with one object per file above, in the order of this contract,
each with `name`, `bytes` and `sha256` (lower-case hex) of the file as written.
