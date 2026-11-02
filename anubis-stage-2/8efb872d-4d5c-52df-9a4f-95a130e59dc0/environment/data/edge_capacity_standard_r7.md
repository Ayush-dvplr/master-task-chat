# Edge cache capacity standard, revision 7

Status: authoritative. This revision replaces the placement optimizer's
built-in assumptions and every earlier revision. When an export, a tool
default, a superseded configuration or an earlier optimizer run disagrees with
this standard, this standard decides. The earlier optimizer run in
`optplan_prev.csv` is known to understate peak usage; it is kept only as the
reported baseline described in section 10 and is never a measurement.

## 1. Planning cut and instants

The planning cut is 2024-10-01T18:00:00Z. Every dated record is read as of the cut: within
any history, the record that applies is the latest one whose instant is at or
before the cut, and records dated after the cut do not apply. Approved
amendments that take effect after the cut are carried as pending (section 6)
and are not part of the frozen figures.

Instants appear as epoch seconds, epoch milliseconds, ISO 8601 with `Z` or a
numeric offset, SQL style timestamps with a `+HH` offset, or dates. A date
without a time means 00:00:00 UTC of that date. Counter readings written as a
plain `YYYY-MM-DD HH:MM:SS` wall time are in the local time of the node's PoP
as of the cut (section 3). Calendar `TZID` values follow the IANA zone
database.

## 2. Node identity

Exports refer to nodes by the canonical id in any letter case, by fully
qualified name, asset tag, serial number, a name the node carried before a
rename, or a legacy short name. A legacy short name is unique only inside its
PoP, so it is qualified by the `pop` value carried on the same record; the
directory stores it as `name@pop`.

The directory export `nodedir_export.ldif` maps `cn`, `assetTag`, `dNSName`,
`legacyName` and `serialNumber` to the entry's `cn`. The overrides in
`ident_overrides.properties` take precedence over the directory: for an
`alias.<kind>.<value>` key, and separately for a `rename.<old>` key, the line
with the highest `rev` wins. Renames are followed until a name has no further
rename; a rename to the same name cancels. Matching is case-insensitive and
the result is the canonical id, written in lower case.

## 3. Points of presence

The PoP registry (`pop_registry.toml`) decides a node's PoP: the latest placement
in state `installed` (any letter case) at or before the cut. PoP references
may use any alias listed in the PoP table. The PoP table also carries
`utc_offset`, `shield_pool`, `ticket_quota`, `spill_budget`, `ram_pin_pct`
(a whole percentage, with or without a `%` sign) and `scope`.

Capacity suffixes: none or `B` means bytes; `KiB`, `MiB`, `GiB`, `TiB` are
powers of 1024; `KB`, `MB`, `GB`, `TB` are powers of 1000.

## 4. Scope

A node is in scope when, as of the cut, all of these hold: its asset status
is `active`, `serving` or `maintenance` (any letter case); its PoP has scope
`prod`; it has no `CONFIRMED` decommission event starting at or before the
cut; its hardware class is not `retired`; its tier is not `x`; and at least
one property it serves has a production exporter instance registered in
`scrape_targets.toml`. An instance listed in `mirror_twins.json` or `labnodes.tsv` is
not a production instance; a node that no production scraper watches is not
managed by the optimizer.

## 5. Class, tier, memory and properties

Class: the latest non-voided row of the hardware class ledger at or before
the cut (any letter case). The class token inside a node id is not
authoritative.

Tier: the latest tier entry at or before the cut for the node in
`tier_assign.xml`; a node with no such entry takes its class default tier.

Memory: the `mem` value on the asset status row that decides the node's
status (the latest row at or before the cut). Memory sizes are binary whatever
the suffix: `G`, `GB` and `GiB` all mean 2^30 bytes, `M`, `MB` and `MiB` mean
2^20 bytes, and a bare number is bytes.

Properties: the class template, meaning the properties whose `location`
blocks sit in the class block of `edgecache_main.conf` for the node's class,
adjusted by the latest property change per property at or before the cut:
`add` makes the property present, `remove` makes it absent, `confirm` changes
nothing.

Property references may be canonical names, aliases from the `[aliases]`
section of `pathmap.ini`, the 2023 names given by the `renamed` lines of
`edgecache_2023.conf`, or a cache path. A cache path resolves through the node's
section of `pathmap.ini` (a node can appear in more than one section under
different references), falling back to the `[catalog]` default paths. The
`[types]` section gives each property's content type.

## 6. Cache policy

The effective policy of a (node, property) pair is built in layers. Each layer
overrides only the directives it sets:

- L0: the global section of `edgecache_main.conf`; a later directive wins.
- L1: the class block location for (class, property) in `edgecache_main.conf`,
  identified by the catalog path of the property.
- L2: approved class-scope amendments effective at or before the cut, in
  effective order, ties broken by change id.
- L3: node blocks, first the node override section of `edgecache_main.conf`, then
  each included file in include order; inside a file a later block wins. A
  node location is identified by the cache path the property uses on that
  node; a location whose path matches no property of the node is ignored.
- L4: approved node-scope amendments effective at or before the cut, in
  effective order, ties broken by change id.

Directives that matter: `versions N`, `refresh hourly|daily|weekly`,
`store-compressed on|off`, `hot-raw on|off`, `codec <name>` (`gzip`, `zstd`,
or `br`, which may be written `brotli`) and `codec-level N`. A layer that sets
`codec` without `codec-level` resets the level to that codec's default (gzip
6, zstd 3, br 4); `codec-level` on its own changes the level of the codec
already in effect. The codec of a pair is written `<codec>:<level>`. Any
other directive changes nothing.

Amendment status is the status in the change register export, replaced by the
latest CAB decision in `cab_minutes.md` dated at or before the cut that approves or
rejects the change; deferred decisions change nothing. An amendment carries
either a `value` or a `value_ref` naming a proposal in `tuning_drafts.jsonl`, whose
value applies whatever the proposal's state. Fields are `versions`,
`refresh`, `store_compressed`, `hot_raw` and `codec`; flag values may be
written `on` and `off`. Amendments aimed at a node out of scope, or at a
property the node does not serve, are ignored; a class-scope amendment counts
only when at least one in-scope node of that class serves the property.
Approved amendments effective after the cut are pending.

## 7. Effective refresh window

A refresh only takes effect when the cache sweeper runs. A node's sweep
interval comes from its lines in `sweeper.crontab` that run `/usr/local/sbin/cache-sweep` against
`/etc/edgecache/edgecache.conf`; commented lines and `--dry-run` runs sweep nothing. A schedule
that fires at least once an hour is hourly, at least once a day is daily,
otherwise weekly. With several running lines the most frequent wins; with
none the node relies on the packaged daily timer, which is daily. The
effective refresh of a pair is the coarser of its policy refresh and the
node's sweep interval.

## 8. Compression ratio

The ratio for (content type, codec) is the arithmetic mean of
`in_bytes / out_bytes` over the trials in `codec_bench.csv` with status `ok` on
corpus `edge24` (codec names, levels, corpus and status may vary in spelling;
a level may carry a `q` prefix), rounded half to even to 2 decimals. The
rounded ratio is the one used in every later calculation.

## 9. Counters and daily volume

Each (node, property) pair has one production exporter instance registered in
`scrape_targets.toml`. Readings are discarded when the instance is listed in
`mirror_twins.json` or `labnodes.tsv`, when the (job, instance) pair is listed in
`stg_jobs.toml`, or when the same reading (node, property, instance, instant and
raw value) is listed in `replay_inject_q3.prom`. Repeated readings of one series
(node, property, instance, job, instant) count once. `edge_tx_bytes_total` and
`cache_served_bytes_total` name the same series. A raw reading is in the instance's
`counter_unit`: bytes when absent, `KiB` meaning 1024 bytes.

The window is the 7 days ending at the cut, both ends included. The increase
over the window adds, for each consecutive pair of kept readings, the
difference when the counter did not go down and the new reading itself when
it went down (a counter reset). Daily volume in bytes is the increase times
86400 divided by the seconds between the first and last kept readings,
rounded half to even. It is null when fewer than two readings remain, and
zero volume is 0, not null.

## 10. Disk and usage

Geometry: the latest `/var/cache/edge` row at or before the cut in
`blkdev_audit.tsv`. Usable bytes are (blocks minus reserved blocks) times the block
size. The reserve column gives `rb=N` blocks, `op=P` percent (floor of blocks
times P over 100) or `-` (the nvme default of 7 percent); sata media reserve
nothing whatever the column says. A block size suffix `k` means 1024.

Base usage: the `/var/cache/edge` line of the latest disk usage snapshot at or
before the cut in the usage collections. `df -k` figures are KiB. `df -h`
figures are binary (`K`, `M`, `G`, `T`) and convert to the floor of number
times unit.

Post-cut usage: the `/var/cache/edge` line of the earliest snapshot after the
cut that has one; null when there is none.

Prior peak: the sum of `peak_kib` over the `q2-final` rows of
`optplan_prev.csv` for the node (a value may carry a `KiB` or `MiB` suffix; a bare
number is KiB); null when the node has no such rows.

## 11. Footprint

For a pair with a daily volume: cycle bytes are the daily volume times 1/24,
1 or 7 for an hourly, daily or weekly effective refresh, rounded half to even.
One compressed generation is the ceiling of cycle bytes over the ratio. Hot
bytes are the cycle bytes when the pair does not store compressed or keeps
its hot generation raw, otherwise one compressed generation. Stale bytes are
versions minus 1 generations, each compressed when the pair stores compressed
and otherwise the cycle bytes. Peak bytes are hot bytes plus stale bytes plus
the cycle bytes of the refill in progress. Each KiB figure is its own byte
figure divided by 1024 and rounded half to even.
