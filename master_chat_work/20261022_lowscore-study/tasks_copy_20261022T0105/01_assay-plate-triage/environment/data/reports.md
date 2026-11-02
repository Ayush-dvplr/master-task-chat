# The three reports

The engine writes three files into its output directory. The `example_a_out_` and
`example_b_out_` files in this directory are those three, for the two mode zero
runs, under prefixed names.

## readings.jsonl

One JSON object per line, one line per resolved read, in the order the engine
resolved them. Every object carries exactly these nine keys.

| Key | Type | Content |
|---|---|---|
| `action` | string | the read's action, copied through |
| `drift_before` | integer | the plate's drift at the moment the read resolved |
| `grade` | string | `high`, `mid`, `low` or `trace` |
| `operator` | string | the read's operator, copied through |
| `plate` | string | the read's plate, copied through |
| `seq` | integer | the read's sequence number, copied through |
| `status` | string | `setup`, `masked`, `reject`, `review` or `ok` |
| `value` | integer | the figure the chain produced for this read |
| `well` | string | the read's well, copied through |

Each line is `json.dumps(record, sort_keys=True, separators=(",", ":"))` followed
by a newline.

## plates.json

A single JSON object with one key, `plates`, holding the list of per plate rows
sorted by `plate`. Every row carries exactly these twelve keys.

| Key | Type | Content |
|---|---|---|
| `blank_end` | integer | the plate's blank level after its last resolved read |
| `disposition` | string | `quarantine`, `hold` or `release` |
| `drift_end` | integer | the plate's drift after its last resolved read |
| `grades` | object | counts of `high`, `low`, `mid` and `trace` over the plate's resolved reads |
| `measured` | integer | how many of the plate's resolved reads carry the `measure` action |
| `peak` | integer | the largest `value` among the plate's counted reads, or zero |
| `plate` | string | the plate identifier |
| `reads` | integer | how many of the plate's reads were resolved |
| `rejects` | integer | the plate's strike count after its last resolved read |
| `reviewed` | integer | how many of the plate's resolved reads landed on `review` |
| `top_well` | string or null | the well of the counted read carrying the largest `value`, or null when the plate has no counted read |
| `value_total` | integer | the sum of `value` over the plate's counted reads |

A plate's counted reads are the ones whose `status` sits in the set the engine
counts. Which statuses those are is one of the missing constants.

When two counted reads on a plate carry the same `value`, one fixed tie break
decides which well `top_well` names.

The `disposition` ladder is ordered: the quarantine test is applied first, the
hold test second, and `release` is what is left.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## bench.json

A single JSON object carrying exactly these seven keys.

| Key | Type | Content |
|---|---|---|
| `by_grade` | object | counts of `high`, `low`, `mid` and `trace` over every resolved read |
| `by_status` | object | counts of `masked`, `ok`, `reject`, `review` and `setup` over every resolved read |
| `plates` | integer | how many plates the run has |
| `quarantined` | array | the sorted identifiers of the plates whose disposition is `quarantine` |
| `reads` | integer | how many reads were resolved |
| `top_plate` | string or null | the plate carrying the largest `value_total`, or null on an empty run |
| `value_total` | integer | the sum of `value_total` over every plate |

When two plates carry the same largest `value_total`, one fixed tie break decides
which plate `top_plate` names.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## The digests in manifest.json

Both digests are lowercase hex sha256 over UTF-8 text built from the three
reports above.

`plate_digests` maps each plate identifier to the digest of that plate alone. The
text digested is the plate's own lines of `readings.jsonl`, in resolution order
and in the byte form given above, followed by that plate's row from
`plates.json`, serialized on its own as
`json.dumps(row, sort_keys=True, indent=2)` plus a newline.

`run_digest` is the digest of the whole run: the complete text of
`readings.jsonl`, then the complete text of `plates.json`, then the complete text
of `bench.json`, concatenated in that order.

The two mode zero runs let a digest routine be checked before it is trusted:
recompute both digests from the shipped `example_a_out_` files and they will
match `example_a_manifest.json`.
