# Gauging and revision dictionary

## Gauging exports

A gauging of the season is recorded in exactly one of the three gauging exports. The exports name the same five facts differently:

| Fact | `gx_a.csv` | `gx_b.tsv` | `gx_c.jsonl` |
|---|---|---|---|
| gauging id | `gauging_id` | `gid` | `id` |
| licence code | `licence` | `lic` | `licence` |
| from station code | `from_stn` | `upper` | first item of `ends` |
| to station code | `to_stn` | `lower` | second item of `ends` |
| sense | `sense` | `drawn_upper` | `drawn_by` |

`gx_a.csv` is comma-separated values as RFC 4180 defines them, with a header line; its `sense` is `fwd` (the canal carried water from the from station into the to station, so the to station drew), `rev` (the from station drew) or `nil` (neither drew). `gx_b.tsv` is tab-separated with a header line; its `drawn_upper` is the from station's draw points: `1`, `0` or `0.5`. `gx_c.jsonl` holds one JSON object per line; its `drawn_by` is `from`, `to` or `neither`. The same gauging id appearing in two exports, or twice in one export, breaks the export rules.

## Draw points

In a gauging, the reservoir that drew scores 1 draw point and the other 0; when neither drew, each scores 1/2.

## Revisions

`rv_log.psv` is pipe-separated with the header `seq|gauging_id|action|value`. `seq` is a positive integer, unique in the log; the lines are not stored in `seq` order. `action` is `sense` or `void`; for `sense` the `value` is a sense in the `gx_a.csv` notation, and for `void` the value is empty.

Only revisions whose `seq` is at or below the revision cutoff apply. For each gauging, the applying revision with the highest `seq` that names the gauging decides the gauging's net state: a `sense` revision gives the gauging that sense, and a `void` revision removes the gauging. A gauging no applying revision names keeps the sense its export records. A revision naming a gauging id that no export holds changes nothing.

## Net gaugings

The net gaugings of the season are the gaugings of the three exports in their net state, voided gaugings left out. Every net gauging counts once in balancing and once in loss accounting.
