# Result-cache capacity planning rulebook, revision 5

This rulebook is the authority for how a result-cache node plan is computed. Where a
saved advisor query, a circulated calendar, a draft digest, an announcement, a cache,
a hint, a dashboard export or a published plan disagrees with this rulebook, the
pricing bulletin or the capacity workbook, those three win and the other material is
wrong. Sections are referred to elsewhere as P1, P2 and so on. Revision 5 replaces
revision 4: it dates the merge ledger, adds the adoption register, the rounding
stages, the `RETAG` adjustment and the cluster commitment pass.

## P1. Identifiers

1. Query ids, project tokens, reservation ids, template ids, team codes and pool ids
   are compared after removing leading and trailing whitespace (and quotes left by
   loosely written YAML) and converting to upper case. Every such id written to an
   output uses that form.
2. Family codes and warehouse sizes are compared case insensitively and are written in
   lower case. An engine is `family.size`.
3. Cluster tokens are mapped to a canonical cluster through `cluster_aliases.yaml`
   (`alias` to `canonical`, aliases compared per P1.1). A token that is not an alias
   is used as it is, per P1.1. Every cluster written to an output is the canonical
   code.
4. `project_merges.psv` maps a `from_project` to the project it was `merged_into`.
   A ledger row is in effect from 00:00:00 of its `merged_on` date, read as wall time
   at `billing_offset` of the planning profile, onwards; that instant itself is in
   effect. A project token is resolved as of an instant: start at the token; while the
   current id is the `from_project` of a row in effect at that instant, step to its
   `merged_into` and count one hop. When a step arrives at an id the walk has already
   visited, the walk stops: the token resolves to the smallest id (plain string
   comparison) among the ids of the cycle, and the hop count is the number of steps
   taken. Otherwise the token resolves to the id where the walk stops. A
   `from_project` appears on one ledger row only.
5. The instant used by P1.4 is the start of the query for the project token of a live
   query (as it stands after P4, so a `MOVE` or `ADD` token is resolved as of the
   query's start). Every other project token, namely the `dev_projects` of the profile,
   reservation owners and the ledger report of the output contract, is resolved as of
   `W1` (P5).
6. The family of a query is the family that Appendix T of `feed_layouts.md` lists for
   its template id. The letters in front of the dash of a template id do not name the
   family.
7. A pool is one family in one canonical cluster. Its id is the family in upper case,
   `@`, and the cluster, for example `OLAP@WH-EUW1`. Pools are ordered by pool id
   (plain string comparison); families are ordered by their upper-case code; clusters
   by their canonical code.

## P2. Which files are feeds

Only the files listed under `shards` in `ingest_manifest_r7.json` are query-log feeds.
A file that looks like a query-log export but is not listed is not a feed. Each shard
entry names a `layout` (record shapes in `feed_layouts.md`), a `ts_convention`, a
`qty_unit`, an `option_codes` map and a `status_codes` map.

1. `option_codes` maps the cache option code a layout writes to `S` (scanned on the
   warehouse), `C` (served by an existing cache reservation) or `B` (batch,
   preemptible). `status_codes` maps the status code to `F` (final) or `V` (voided).
   Codes are compared after stripping whitespace, case sensitively.
2. `qty_unit` is `gib`, `mib`, `kib` or `cgib` (hundredths of a GiB). A scanned volume
   is converted to GiB exactly: divide by 1, 1024, 1048576 or 100. Volumes are never
   rounded, and a value written as a JSON number means the decimal it prints as.
3. Timestamp conventions:
   - `iso_z`: `YYYY-MM-DDTHH:MM:SSZ`, UTC.
   - `iso_offset`: ISO 8601 with an explicit numeric offset; convert to UTC.
   - `epoch_s`: integer seconds since 1970-01-01T00:00:00Z.
   - `epoch_ms`: integer milliseconds since 1970-01-01T00:00:00Z.
   - `compact_utc`: `YYYYMMDDHHMMSS`, UTC.
   - `local_cluster`: wall-clock date and time with no offset, at the fixed UTC offset
     of the query's own canonical cluster, taken from the `Clusters` sheet of the
     capacity workbook.
   - `local_billing`: wall-clock date and time with no offset, at `billing_offset` of
     the planning profile.
   Offsets are fixed; there is no daylight saving anywhere.

## P3. Live queries

Apply these steps to every data row of every listed shard, in this order.

1. Count the row as read.
2. Several rows may carry the same query id, in the same shard or in different
   shards. Keep only the row with the largest `revision`; every other row with that id
   is a duplicate and is dropped whatever its content or status.
3. A kept row whose status maps to `V` is voided and dropped. The other kept rows are
   the live queries. A shard's kept count is the number of live queries whose kept row
   came from that shard.

Each live query has a query id, a UTC start, a project token, a cluster token, a
template id, a warehouse size, a scanned volume in GiB and a cache option letter.

## P4. Scan adjustments

`scan_adjustments.jsonl` and `scan_adjustments_late.xml` are two halves of one
journal. Merge them and apply only entries whose `status`, compared case
insensitively, is `posted`, in ascending `seq` order. `seq` values are unique across
both files. Each entry acts on the live queries as they stand after the earlier
entries.

- `VOID` removes the query.
- `SETQTY` replaces the query's scanned volume with `quantity_gib` (GiB).
- `MOVE` replaces the query's project token with `project`.
- `RETAG` replaces the query's template id with `template`.
- `ADD` creates a query with the given id, UTC `usage_start_utc`, `project`,
  `cluster`, `template`, `size`, `quantity_gib` and option letter (`S`, `C` or `B`,
  written literally).
- `VOID`, `SETQTY`, `MOVE` and `RETAG` on an id that is not live have outcome
  `skipped_missing`; `ADD` of an id that is live has outcome `skipped_duplicate`.
  Every other posted entry has outcome `applied`.

A query voided earlier can be created again by a later `ADD`, and a `SETQTY` that
comes after a `VOID` of the same id finds nothing.

## P5. Lookback window and hours

`W0` and `W1` are `lookback_start_local` and `lookback_end_local` of the planning
profile read as wall time at `billing_offset` and converted to UTC. The lookback is
the half-open interval `[W0, W1)` and holds `H = (W1 - W0) / 1 hour` hours. A query
whose start is outside it is out of window and takes no further part. A query at time
`t` belongs to hour index `floor((t - W0) / 1 hour)`, counted from 0.

`outage_windows` in the profile lists outages by cluster, with `from_local` and
`to_local` read as wall time at `billing_offset`. Hour `h` of a cluster is an outage
hour when its start `W0 + h hours` lies in `[from, to)` of a window of that cluster.
The valid hours of a pool are the hours of the lookback that are not outage hours for
the pool's cluster. Every valid hour counts in P10 to P12 even when the pool has no
usage in it.

## P6. Projects in scope

`proj_registry_main.csv` and `proj_registry_archive.tsv` list projects with different
column names for the same facts (`feed_layouts.md`). When a project appears in both
exports, the main export row is used and the archive row is ignored. A resolved
project is checked in this order:

1. `UNKNOWN_PROJECT`: it is in neither export.
2. `OTHER_ORG`: its org is not `org_id` of the profile.
3. `CLOSED_PROJECT`: its status (case insensitive) is `CLOSED` and its closed date is
   earlier than the date of `lookback_start_local`.
4. `DEV_PROJECT`: it is in the profile's `dev_projects` list after that list is
   resolved per P1.4 and P1.5. The registry `tier` column is informational and is not
   used.

A project that passes all four checks is in scope.

## P7. Query exclusion

Every in-window live query, in query id order, is excluded with the first reason that
applies:

1. the project reason of P6 for its project resolved as of its start;
2. `CLUSTER_OUT_OF_SCOPE`: its canonical cluster is not in `clusters_in_scope` of the
   profile (tokens mapped per P1.3);
3. `INELIGIBLE_FAMILY`: its family (P1.6) is missing from the ruleset sheet in force
   or its `eligible` flag is false;
4. `BATCH_QUERY`: its option is `B`;
5. `OUTAGE_HOUR`: its hour is an outage hour for its cluster (P5).

Every other in-window live query is included. Queries with option `C` are included:
they are load that an existing reservation serves today, and existing reservations
are taken into account by P9 and P10, never by dropping queries.

## P8. Scan units

The usage of a query in normalized units is its scanned volume in GiB times the
`normalized_factor` of its engine (`family.size`, family per P1.6) on the
`ScanFactors` sheet of the capacity workbook, rounded to three decimals, half to even.
This rounding is applied to every query on its own, before any sum. Factors are exact
decimals; `max` sizes have family-specific factors. A pool's usage in hour `h` is the
sum of the rounded usage of its included queries in that hour. A project's usage in a
pool is the sum of the rounded usage of its included queries in the pool, under the
project each query resolves to as of its start. Pools are the family and cluster
pairs that have at least one included query.

## P9. Existing reservations

`cache_reservations.xml` lists the cache reservations the org already holds. Table
C-1 of the pricing bulletin records committee rulings by reservation id. A
reservation's effective end is the revised time of an `EXTENDED` ruling, else its
`end_utc`. Its pool id is built from its `family` and canonical `cluster` per P1.7
whether or not that pool exists. Its owner is resolved as of `W1`. Each reservation
gets the first status that applies:

1. `CANCELLED`: Table C-1 rules it cancelled.
2. `NOT_ACTIVE`: its `state` (case insensitive) is not `ACTIVE`.
3. `OWNER_OUT_OF_SCOPE`: its resolved `owner` fails P6.
4. `NO_POOL`: its cluster is not in scope or its family is not eligible.
5. `LAPSES`: its effective end is earlier than `horizon_end_utc` of the profile.
6. `NETTED`: every other reservation.

A pool's netted units are the sum of the `units` of its `NETTED` reservations.

## P10. Planning load

The grown usage of a pool in valid hour `h` is `usage(h) x (100 + growth_pct) / 100`
rounded to two decimals, half to even. The planning load is
`max(0, grown usage - netted units)`. Growth is applied to the usage first; the
netted units are taken off after the rounding.

## P11. Rates and constants

1. Table R-2 of the pricing bulletin gives, for each family and canonical cluster, the
   scan rate and the node rate in cents. Table R-1 in the same bulletin is withdrawn.
2. Table E-1 lists errata. Errata are taken in ascending `erratum_id` order (plain
   string comparison). An erratum whose status is `IN FORCE` replaces the named field
   (`scan_rate_cents` or `node_rate_cents`) of the Table R-2 row of its family and
   cluster (compared per P1), so a later erratum in force on the same field wins over
   an earlier one; a `RESCINDED` erratum has no effect. Rates are used exactly as
   printed.
3. All planning constants named in P7 and P10 to P14 (`eligible`, `node_units`,
   `min_nodes`, `family_cap`, `growth_pct`, `tier_units`, `tier_discount_pct`,
   `mem_units_per_node`, `node_cap_total`, `mem_budget_units`, `saving_rounding`) come
   from the ruleset sheet in force of `capacity_workbook_fy26.xlsx`. Sheet names live
   in the workbook, not in the worksheet file names. A numeric value stored as text is
   read after stripping whitespace. `eligible` is true when the value, compared case
   insensitively, is `y`, `yes`, `true` or `1`.
4. The ruleset sheet in force is chosen by the `Adoptions` sheet of the workbook. Among
   its rows whose `track` equals `ruleset_track` of the profile and whose `status` is
   `ADOPTED`, take the row with the latest `effective` date that is on or before the
   date of `lookback_start_local`; its `sheet` is the sheet in force and its
   `adoption_id` is the adoption in force. No two `ADOPTED` rows of one track share an
   `effective` date. `WITHDRAWN` and `PROPOSED` rows have no effect.
5. `effective` cells hold date serial numbers. The workbook states its date system in
   the `workbookPr` element of `xl/workbook.xml`: when `date1904` is `1` or `true`,
   serial N is the date N days after 1904-01-01; otherwise serial N is the date N days
   after 1899-12-30.

## P12. Node levels and saving

Cache is bought in nodes of `node_units` normalized units of the pool's family.

1. `kmax` is the largest whole number of nodes whose units do not exceed the pool's
   largest planning load over its valid hours.
2. A pool whose largest planning load is 0 is excluded with reason `NO_RESIDUAL`. A
   pool whose `kmax` is below `min_nodes` is excluded with reason `BELOW_MIN_NODES`.
   Every other pool is a candidate pool.
3. A candidate pool may hold 0 nodes or any whole number of nodes from `min_nodes` to
   `kmax`.
4. With `k` nodes the cache units are `c = k x node_units`. The served unit-hours are
   the sum over the valid hours of `min(load(h), c)`.
5. The effective node rate is the node rate of P11 when `c` is below the family's
   `tier_units`. When `c` is at or above `tier_units`, the whole reservation, every
   unit of it, is priced at the discounted rate: node rate x (100 -
   `tier_discount_pct`) / 100, rounded to four decimals, half to even.
6. The saving in cents is `scan_rate x served - effective_rate x valid_hours x c`, an
   exact decimal.
7. A pool holding `k` nodes uses `k x mem_units_per_node` memory units of its family.

## P13. The plan

A plan gives every candidate pool a node count allowed by P12.3, with every pool of a
closed cluster (P13A) at 0 nodes, such that:

1. the nodes of the pools of each family sum to at most that family's `family_cap`;
2. the nodes of all pools sum to at most `node_cap_total`;
3. the memory units of all pools (P12.7) sum to at most `mem_budget_units`;
4. the sum of the exact savings is the largest any such assignment reaches.

When two assignments reach the same largest sum, the one with fewer nodes in total
wins; when they also tie on nodes, the one with fewer memory units wins; when they
also tie on memory, compare the node counts of the families in family order and take
the assignment with fewer nodes in the first family that differs; within a family,
compare the pools in pool order the same way.

## P13A. Cluster commitments

Table M-1 of the pricing bulletin gives each listed canonical cluster a `min_nodes`
commitment. A cluster that Table M-1 does not list has no commitment. Table M-0 is
superseded and has no effect.

Start with no closed cluster and find the plan of P13. A cluster is short when the
pools of that cluster hold at least one node in total and fewer than its `min_nodes`.
When no cluster is short, that plan is the plan in force. Otherwise close exactly one
cluster: the short cluster whose pools have the smallest sum of exact savings (P12.6)
at their planned nodes, ties broken by cluster code ascending. Then find the plan of
P13 again with every closed cluster held at 0 and check again. Each closing is one
round. The pools of closed clusters stay candidate pools at 0 nodes.

## P14. Reporting

1. A pool's `saving_cents` is its exact saving at its planned nodes rounded to a whole
   cent per `saving_rounding` (`half_even`). Family and cluster rollups sum the pools'
   rounded `saving_cents`.
2. `total_saving_cents` of the plan is the sum of the exact savings of all candidate
   pools, rounded once to a whole cent half to even. It can differ from the sum of the
   rounded pool savings.
3. `served_pct` is served unit-hours / the sum of the planning load over the valid
   hours x 100. `utilization_pct` is served unit-hours / (c x valid hours) x 100 and
   is empty for a pool with 0 nodes. Both are rounded to two decimals half to even and
   always written with two decimals.

## P15. Chargeback

The rounded `saving_cents` of each pool with at least one node is allocated to the
projects with usage in that pool (P8, before growth), in proportion to their usage.
Each project first gets its exact share rounded down to a whole cent. The cents left
over are given one each to the projects with the largest fractional remainders, ties
broken by project id ascending, until none remain.

## P16. Worked examples

All figures below are made up for illustration; none of them comes from the shipped
files.

- Levels and saving. A pool with three valid hours of planning load 10, 25 and 40
  units, `node_units` 8, `min_nodes` 2, scan rate 5.0000 and node rate 3.0000 cents:
  `kmax` is 5 (40 / 8). The allowed levels are 0, 2, 3, 4 and 5 nodes. At 3 nodes
  (`c` = 24) the served unit-hours are 10 + 24 + 24 = 58 and the saving is
  5 x 58 - 3 x 3 x 24 = 74 cents. At 5 nodes (`c` = 40) it is 5 x 75 - 3 x 3 x 40 =
  15 cents. With `mem_units_per_node` 3 the pool uses 15 memory units at 5 nodes.
- Tier rate. With node rate 3.0007, `tier_units` 32 and `tier_discount_pct` 9, the
  4 and 5 node levels above are priced at 3.0007 x 91 / 100 = 2.730637, rounded to
  2.7306 cents for all of their units.
- Units. A query of 3072 MiB on an `olap.max` engine whose factor is 128 has a usage
  of 3 x 128 = 384 units. A query of 1000000 KiB on a `geo.l` engine whose factor is 2
  has a usage of 0.95367431640625 x 2 = 1.9073486328125, rounded to 1.907 units; two
  such queries in one hour give 3.814 units, not 3.815.
- Load. A usage of 20.105 units with a growth of 8 percent grows to 21.7134, rounded
  to 21.71; with 4.5 netted units the load is 17.21.
- Dated merges. Ledger rows `MGA -> PJB` dated 2026-03-10 and `PJB -> PJC` dated
  2026-03-12 with `billing_offset` +05:30: the first is in effect from
  2026-03-09T18:30:00Z. A query by `MGA` starting 2026-03-11T00:00:00Z resolves to
  `PJB` with 1 hop; one starting 2026-03-12T00:00:00Z resolves to `PJC` with 2 hops;
  one starting 2026-03-09T18:29:59Z stays `MGA` with 0 hops.
- Cycle. Rows `PJK -> PJE` and `PJE -> PJK`, both in effect: `PJK` walks to `PJE` and
  back to `PJK`, a cycle of `PJE` and `PJK`, so it resolves to `PJE` with 2 hops; a
  token `MGZ -> PJK` resolves to `PJE` with 3 hops.
- Adoption. With the 1904 date system, serial 45000 is 2027-03-16 (45000 days after
  1904-01-01) and serial 44999 is 2027-03-15. If a track has `ADOPTED` rows effective
  on serials 44990 (2027-03-06) and 45001 (2027-03-17) and the lookback starts on
  2027-03-16, the row with 44990 is in force; had the lookback started on 2027-03-17,
  the row with 45001 would be.
- Commitments. Clusters X and Y are short in a plan, with exact savings 900.5 and
  410.25 at their planned nodes: Y is closed and the plan is found again. If X is now
  at or above its commitment, that plan is in force after one round.
