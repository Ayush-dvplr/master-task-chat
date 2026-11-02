# The three reports

The engine writes three files into its output directory. Two of them survive for
the recorded run: `ref_partitions.json` and `ref_catalog.json` in this directory
are the per partition rollup and the catalogue rollup under their reference
names. The per lookup probe ledger for that run was not kept, so nothing here
shows the resolved figures of any single lookup.

## probes.jsonl

One JSON object per line, one line per lookup, in ascending `seq`. Every object
carries exactly these nine keys.

| Key | Type | Content |
|---|---|---|
| `analyst` | string | the lookup's analyst, copied through |
| `band` | string | `heavy`, `warm`, `light` or `idle` |
| `cost` | integer | the figure the chain settled on for this lookup |
| `debt_before` | integer | the index's debt at the moment the lookup resolved |
| `partition` | string | the lookup's partition, copied through |
| `query` | string | the lookup's query, copied through |
| `seq` | integer | the lookup's sequence number, copied through |
| `status` | string | `setup`, `locked`, `dropped`, `flagged` or `ok` |
| `verb` | string | the lookup's verb, copied through |

Each line is `json.dumps(record, sort_keys=True, separators=(",", ":"))` followed
by a newline.

## partitions.json

A single JSON object with one key, `partitions`, holding the list of per
partition rows. The rows run in one fixed order the engine applied; that order is
not alphabetical and is one of the constants to recover. Every row carries
exactly these eleven keys. The index's debt and credit are not part of the row.

| Key | Type | Content |
|---|---|---|
| `bands` | object | counts of `heavy`, `idle`, `light` and `warm` over the partition's lookups |
| `baseline_end` | integer | the baseline of the index the partition names, after the run's last lookup |
| `cost_total` | integer | the sum of `cost` over the partition's counted lookups |
| `disposition` | string | `stalled`, `held` or `open` |
| `fetched` | integer | how many of the partition's lookups carry the `fetch` verb |
| `flagged` | integer | how many of the partition's lookups resolved to `flagged` |
| `lookups` | integer | how many lookups the partition has |
| `misses` | integer | the miss count of the index the partition names, after the run's last lookup |
| `partition` | string | the partition identifier |
| `peak_cost` | integer | the largest `cost` among the partition's counted lookups, or zero |
| `top_query` | string or null | the query of the counted lookup carrying the largest `cost`, or null when the partition has no counted lookup |

A partition's counted lookups are the ones whose `status` sits in the set the
engine counts. Which statuses those are is one of the missing constants.

When two counted lookups on a partition carry the same `cost`, one fixed tie
break decides which query `top_query` names.

The `disposition` ladder is ordered: the stalled test is applied first, the held
test second, and `open` is what is left.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## catalog.json

A single JSON object carrying exactly these seven keys.

| Key | Type | Content |
|---|---|---|
| `by_band` | object | counts of `heavy`, `idle`, `light` and `warm` over every lookup in the run |
| `by_status` | object | counts of `dropped`, `flagged`, `locked`, `ok` and `setup` over every lookup in the run |
| `cost_total` | integer | the sum of `cost_total` over every partition |
| `lookups` | integer | how many lookups the run has |
| `partitions` | integer | how many partitions the run has |
| `stalled` | array | the sorted identifiers of the partitions whose disposition is `stalled` |
| `top_partition` | string or null | the partition carrying the largest `cost_total`, or null on an empty run |

When two partitions carry the same largest `cost_total`, one fixed tie break
decides which partition `top_partition` names.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.
