# Placement optimizer output contract

This contract fixes the shape of everything `/app/out/build.py` writes and how
the second and third phases are computed. Phase 1 figures follow
`edge_capacity_standard_r7.md`.

## Program

    python3 /app/out/build.py phase1 <DATA_DIR> <P1_DIR>
    python3 /app/out/build.py phase2 <P1_DIR> <P2_DIR>
    python3 /app/out/build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>

Exit status 0 on success. Exit status 2 for a wrong subcommand or a wrong
number of arguments; the first stderr line is then `error: usage: ` followed
by a short reason. Exit status 3 when an input or upstream directory is
missing, unreadable, or lacks one of the files the phase needs; the first
stderr line is then `error: upstream: ` followed by the offending path. A
failed run writes no output files.

## Common format rules

- UTF-8, LF line endings, a final newline, no byte order mark.
- CSV: comma separated, one header line exactly as listed, no quoting, no
  spaces around values. Null is an empty field. Booleans are `1` and `0`.
  Integers are plain base 10. Decimal fields are written with the stated
  number of places, rounded half to even.
- JSON: `json.dumps(obj, indent=2, sort_keys=True)` followed by one newline;
  null is JSON `null`.
- Rounding to KiB or MiB is half to even. MiB fields are a KiB total divided
  by 1024 unless stated otherwise.
- Names are written in their canonical lower-case form: node ids, PoP codes
  (the keys of the PoP table), class names, property names (the `[catalog]`
  names), tiers, refresh windows, media and codec names (`gzip`, `zstd`,
  `br`), whatever spelling the source used.
- Instants are written `YYYY-MM-DDTHH:MM:SSZ` and dates `YYYY-MM-DD`.
- Ordering is byte order of the stated key unless stated otherwise.

## Phase 1 (`p1/`)

`nodes.csv`: `node_id`, `pop`, `class`, `tier`, `media`, `usable_bytes`, `base_used_bytes`, `post_cut_used_bytes`, `prior_peak_kib`, `sweep_interval`, `ram_bytes`. One row per in-scope node, ordered by
`node_id`. `usable_bytes`, `base_used_bytes`, `post_cut_used_bytes` and
`ram_bytes` are bytes; `prior_peak_kib` is KiB; `sweep_interval` is the sweep
interval.

`properties.csv`: `node_id`, `property`, `instance`, `samples`, `daily_bytes`. One row per (node, property) pair
of an in-scope node, ordered by node then property. `instance` is the pair's
production instance; `samples` is the number of kept in-window readings;
`daily_bytes` is the daily volume or null.

`policies.csv`: `node_id`, `property`, `versions`, `refresh`, `effective_refresh`, `store_compressed`, `hot_raw`, `codec`, `ratio`. Same rows and order. `refresh` is the
policy refresh, `effective_refresh` the refresh after the sweep interval cap,
`codec` is `<codec>:<level>`, `ratio` has 2 decimals.

`footprints.csv`: `node_id`, `property`, `cycle_bytes`, `hot_kib`, `stale_kib`, `peak_kib`. Same rows and order; every value
field is null when `daily_bytes` is null.

`pending.json`: an object with `freeze_utc` (the cut, `YYYY-MM-DDTHH:MM:SSZ`)
and `amendments`, a list of the pending amendments ordered by
`effective_utc` then `id`. Each entry has `id`, `scope` (`node` or `class`),
`node_id` (null for class scope), `class` (null for node scope), `property`,
`field`, `value` (integer for versions, string for refresh, boolean for
store_compressed and hot_raw) and `effective_utc`.

`pops.json`: an object with `pops`, a list ordered by `pop` of the prod PoPs,
each with `pop`, `utc_offset_minutes`, `shield_pool_kib`, `ticket_quota`,
`spill_budget_kib`, `ram_pin_pct` (integer), `pin_budget_kib` (the sum over the
PoP's in-scope nodes of the floor of the node's memory in KiB times
`ram_pin_pct` over 100) and `nodes` (in-scope node count).

## Phase 2 (`p2/`), from the six phase 1 files only

Per node, from phase 1: `usable_kib`, `base_kib` and `ram_kib` are the byte
figures in KiB; `peak` is the sum of the node's non-null `peak_kib`;
`daily_kib` is the sum of its non-null `daily_bytes` in KiB, null when none is
measured; `headroom` is `usable_kib - base_kib - peak`. A pair is affected by a
pending amendment when the amendment names its node and property (node scope)
or its node's class and property (class scope). A node is pending when any of
its pairs is affected.

`pop_rollup.csv`: `pop`, `nodes`, `measured_pairs`, `null_pairs`, `compressed_pairs`, `peak_mib`, `usable_mib`, `headroom_mib`, `pending_nodes`, `shield_mib`. One row per PoP of `pops.json`,
same order. `measured_pairs` and `null_pairs` count pairs with and without
`daily_bytes`; `compressed_pairs` counts pairs with `store_compressed` 1;
`peak_mib` is the sum of `peak_kib` in MiB; `usable_mib` and `headroom_mib`
are sums of the per-node KiB figures in MiB; `pending_nodes` counts pending
nodes; `shield_mib` is `shield_pool_kib` in MiB.

`class_rollup.csv`: `class`, `nodes`, `pops`, `daily_mib`, `mean_ratio`, `peak_mib`, `pending_pairs`, `shield_share_mib`. One row per class that has at
least one node, ordered by class. `pops` counts distinct PoPs; `daily_mib` is
the sum of `daily_bytes` divided by 1048576 (null when no pair of the class is
measured); `mean_ratio` is the mean `ratio` over pairs with
`store_compressed` 1, 3 decimals, null when none; `peak_mib` is the sum of
node `peak` in MiB; `pending_pairs` counts affected pairs;
`shield_share_mib` is the sum over PoPs with a positive total peak of
`shield_pool_kib` times the class's peak at the PoP over the PoP's total
peak, computed exactly and then converted to MiB.

`shield_alloc.csv`: `node_id`, `pop`, `demand_kib`, `granted_kib`, `cumulative_kib`, `state`. PoPs in `pops.json` order;
inside a PoP, nodes by tier ascending, then non-pending before pending, then
the order of `nodes.csv`. A node with no measured pair has demand 0, granted 0
and state `unmeasured`. Otherwise demand is the sum of `stale_kib` over pairs
with `store_compressed` 1 and a non-null value, and the grant is the smaller of
demand and what is left of the PoP's `shield_pool_kib`. `cumulative_kib` is the
running total of grants inside the PoP. State: `zero` for demand 0, `full`,
`partial` or `none`.

`pin_plan.csv`: `node_id`, `property`, `density`, `hot_kib`, `cumulative_kib`, `pinned`. The RAM pin plan. Nodes in
`nodes.csv` order. A node's pin budget is the floor of `ram_kib` times its
PoP's `ram_pin_pct` over 100. Its candidates are its pairs with a non-null
`daily_bytes`, an `effective_refresh` other than `hourly`, and no pending
amendment affecting them; a node without candidates has no rows. Candidates
with `hot_kib` 0 come first, by property; the rest follow by density
descending (`daily_bytes` over `hot_kib`, compared exactly), then property.
Walking that order, a candidate is pinned (`1`) when the KiB already pinned on
the node plus its `hot_kib` stays within the budget, and is otherwise skipped
(`0`) while the walk continues. `density` has 2 decimals and is empty when
`hot_kib` is 0; `cumulative_kib` is the KiB pinned on the node after the row.

`risk_rank.csv`: `node_id`, `pop`, `headroom_kib`, `daily_kib`, `days_to_full`, `full_date_local`, `pin_share`, `pending`, `rank`. Days to full: empty when
`daily_kib` is null, `never` when it is 0, `0.00` when headroom is not
positive, otherwise headroom over `daily_kib` with 2 decimals.
`full_date_local` is the PoP-local date (`YYYY-MM-DD`) of the cut plus the
exact unrounded days, using `utc_offset_minutes`, empty unless days are
numeric. `pin_share` is the KiB the pin plan pins on the node over the sum of
the node's non-null `hot_kib`, 4 decimals, empty when that sum is 0.
`pending` is 1 or 0. Rows are ordered by rank: numeric days ascending by the
exact unrounded value, then `never`, then empty, ties by `node_id`; `rank`
counts from 1.

`manifest.json`: `phase` (2), `inputs` (file name to SHA-256 hex of each
phase 1 file's bytes), `totals` (`nodes`, `pairs_measured`, `pairs_null`,
`pairs_compressed`, `peak_kib` as the sum of all `peak_kib`, `daily_kib` as the
sum of all `daily_bytes` in KiB, `pending_amendments` as the number of entries
in `pending.json`, `shield_kib` as the sum of `shield_pool_kib`, `pinned_kib`
as the KiB pinned by the whole pin plan), `median_days_to_full` (median of the
exact numeric days, mean of the two middle values for an even count, as a
string with 2 decimals, null when none) and `p90_headroom_kib` (nearest-rank
90th percentile of node headroom: sort ascending, take position
ceil(0.9 n)).

## Phase 3 (`p3/`), from the six phase 1 and six phase 2 files only

Phase 3 first checks that the phase 2 files belong to the phase 1 files it is
handed: the phase 2 `manifest.json` must have `phase` 2 and an `inputs` map
equal to the SHA-256 of the six phase 1 files' bytes. Otherwise the stage exits
3 with `error: upstream: ` and the manifest path.

The pending amendments are applied here, on top of the phase 1 policy of each
affected pair, in `pending.json` order. For an affected pair with
`daily_bytes`, the footprint is recomputed with the standard's footprint
rule, the new effective refresh (coarser of the new refresh and the node's
`sweep_interval`) and the pair's phase 1 ratio; every other pair keeps its
phase 1 `peak_kib` (null counts as 0). Per node: `peak_now_kib` is the phase 1
peak, `peak_after_kib` the peak after amendments, `prior_gap_kib` is
`peak_after_kib` minus `prior_peak_kib` (empty when `prior_peak_kib` is null),
and `headroom_after_kib = usable_kib - observed_kib - peak_after_kib + shield
grant + pinned KiB`, where `observed_kib` is `post_cut_used_bytes` in KiB when
it is not null and `base_kib` otherwise, the shield grant comes from
`shield_alloc.csv` and the pinned KiB is the sum of `hot_kib` over the node's
pinned rows of `pin_plan.csv` (both 0 when absent).
Days after use the `risk_rank.csv` `daily_kib` and the risk rank rules. The
flag is `at-risk` when days after are numeric and below the phase 2
`median_days_to_full`, otherwise `watch` when `peak_after_kib` exceeds
`peak_now_kib`, otherwise `ok`. `pop_share` is `headroom_after_kib` over the
PoP's `headroom_mib` times 1024 and `class_peak_share` is `peak_after_kib` over
the class's `peak_mib` times 1024, both 4 decimals and empty when the
denominator is not positive. `full_date_after` follows the `full_date_local`
rule.

`projection.csv`: `node_id`, `pop`, `class`, `peak_now_kib`, `peak_after_kib`, `prior_gap_kib`, `headroom_after_kib`, `days_after`, `rank_before`, `flag`, `pop_share`, `class_peak_share`, `full_date_after`, `running_kib`, `running_min_kib`. One row per node in `nodes.csv`
order; `rank_before` is the phase 2 rank; `running_kib` is the running sum of
`headroom_after_kib` in that order and `running_min_kib` the lowest running
sum so far.

`pop_outlook.csv`: `pop`, `headroom_mib_now`, `headroom_mib_after`, `at_risk_nodes`, `shield_left_mib`, `spill_left_mib`, `pending_applied`, `mean_days_after`, `worst_class`. One row per PoP in `pops.json`
order. `headroom_mib_now` is the phase 2 value; `headroom_mib_after` is the
sum of `headroom_after_kib` in MiB; `shield_left_mib` and `spill_left_mib` are
the PoP's pool and budget minus the shield and spill grants of its nodes, in
MiB; `pending_applied` counts pending amendments that affect at least one pair
at the PoP; `mean_days_after` is the mean of the exact numeric days after, 2
decimals, empty when none; `worst_class` is the class whose `at-risk` nodes at
the PoP have the largest sum of exact `class_peak_share` (an empty share counts
as 0), ties by class name, empty when no node is `at-risk`.

`spill_alloc.csv`: `node_id`, `pop`, `deficit_kib`, `daily_kib`, `granted_kib`, `remaining_kib`, `state`. Only nodes with negative
`headroom_after_kib`. PoPs in `pops.json` order; inside a PoP by
`class_peak_share` descending (empty last), then deficit (minus
`headroom_after_kib`) descending, then `node_id`. A tier 3 node in a PoP whose phase 2 `headroom_mib` is
positive is `deferred`: it gets 0 and the budget is untouched. Otherwise the
grant is the smallest of the deficit, what is left of `spill_budget_kib` and,
when it is positive, the phase 2 `p90_headroom_kib`; state `full` when the grant
covers the deficit, `partial` when it is positive but smaller, `none` when it
is 0. `daily_kib` is the
`risk_rank.csv` value and `remaining_kib` the budget left after the row.

`tickets.csv`: `ticket`, `pop`, `node_id`, `flag`, `days_after`, `rank_before`. Per PoP in `pops.json` order, nodes
flagged `at-risk` or `watch` are ordered by flag (`at-risk` first), then days
after (numeric ascending by exact value, then `never`, then empty), then
`class_peak_share` descending (empty last), then `pop_share` descending (empty
last), then `node_id`; the first `ticket_quota` of them get tickets
`T-<pop>-01`, `T-<pop>-02` and so on, and a PoP whose phase 2 `headroom_mib` is
not positive issues up to twice its `ticket_quota`.

`class_drift.csv`: `class`, `peak_mib_now`, `peak_mib_after`, `drift_mib`, `prior_gap_mib`, `at_risk_nodes`, `mean_pop_share`, `shield_share_after_mib`. One row per class in
`class_rollup.csv` order. `peak_mib_now` is the phase 2 `peak_mib`;
`peak_mib_after` is the class's summed `peak_after_kib` in MiB; `drift_mib` is
after minus now; `prior_gap_mib` is the sum of the class's non-empty
`prior_gap_kib` in MiB, empty when none; `at_risk_nodes` counts flagged nodes; `mean_pop_share` is the
mean of non-empty `pop_share` values, 4 decimals; `shield_share_after_mib`
follows the `shield_share_mib` rule with `peak_after_kib` in place of the
phase 1 peak.

`manifest.json`: `phase` (3), `inputs` (keys `p1/<file>` and `p2/<file>` for all
twelve upstream files, SHA-256 hex of their bytes), `totals` (`nodes`;
`at_risk` and `watch` as the number of nodes with each flag; `peak_after_kib`
and `headroom_after_kib` as sums over all nodes; `spill_granted_kib` as the sum
of spill grants; `tickets` as the number of tickets issued; `pending_applied`
as the number of pending amendments that affect at least one pair) and
`chain`: start from 64 zeros, then for each data line of `projection.csv` in
order (without its newline) replace the chain with the SHA-256 hex of the
chain followed by the line.
