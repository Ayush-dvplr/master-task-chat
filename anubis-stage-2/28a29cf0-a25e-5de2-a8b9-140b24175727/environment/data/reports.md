# The four reports

The gate writes four files into its output directory.
`example_verdicts.jsonl` in this directory is the first of the four as the gate
wrote it for the first worked shift. The four files with a `calibration_`
prefix are the complete report set for the second worked shift. For the
recorded shift `digest.json` carries digests of all four rather than the files
themselves.

A shift may hold no endpoint and no probe at all. The gate still writes all four
files for it: `verdicts.jsonl` empty, `endpoints.json` carrying an empty list,
`precision.csv` carrying its header line and nothing else, and `shift.json`
carrying zero in every count, an empty `quarantined` list and a null
`top_endpoint`.

## verdicts.jsonl

One JSON object per line, one line per probe, in ascending `seq`. Every object
carries exactly these ten keys.

| Key | Type | Content |
|---|---|---|
| `backlog_before` | integer | the endpoint's backlog at the moment the probe resolved |
| `band` | string | `saturate`, `high`, `base` or `idle` |
| `caller` | string | the probe's caller, copied through |
| `endpoint` | string | the probe's endpoint, copied through |
| `mode` | string | the probe's mode, copied through |
| `phase` | string | the probe's phase, copied through |
| `score` | integer | the figure the chain produced for this probe |
| `seq` | integer | the probe's sequence number, copied through |
| `tag` | string | the probe's tag, copied through |
| `verdict` | string | `setup`, `void`, `rejected`, `flagged` or `ok` |

Each line is `json.dumps(record, sort_keys=True, separators=(",", ":"))`
followed by a newline.

## endpoints.json

A single JSON object with one key, `endpoints`, holding the list of per endpoint
rows sorted by `endpoint`. Every row carries exactly these twelve keys.

| Key | Type | Content |
|---|---|---|
| `backlog_end` | integer | the backlog the endpoint held when the shift ended |
| `bands` | object | a count per band name, all four keys always present |
| `budget_end` | integer | the budget the endpoint held when the shift ended |
| `counted` | integer | how many of the endpoint's probes counted into its total |
| `disposition` | string | `quarantine`, `throttle` or `clear` |
| `endpoint` | string | the endpoint identifier |
| `flagged` | integer | how many of the endpoint's probes resolved to `flagged` |
| `probes` | integer | how many probes the endpoint carried |
| `score_total` | integer | the sum of the counted probes' scores |
| `strikes` | integer | how many strikes the endpoint gathered |
| `top_score` | integer | the largest score among the counted probes, or zero |
| `top_tag` | string or null | the tag of the counted probe carrying the largest score |

Which verdicts count into `counted`, `score_total`, `top_score` and `top_tag`,
how the `top_tag` tie is broken, which strike count quarantines an endpoint and
which backlog figure throttles one are all missing constants.

## precision.csv

One header line and one row per precision the shift charged against, sorted by
precision name. No quoting, no padding, one trailing newline.

```text
precision,endpoints,probes,score_total,flagged
```

Each row carries the precision name and then four integers: how many endpoints
were charged at it, how many probes those endpoints carried, the sum of their
`score_total`, and the sum of their `flagged`.

## shift.json

A single JSON object carrying exactly these seven keys.

| Key | Type | Content |
|---|---|---|
| `by_band` | object | a count per band name over every probe |
| `by_verdict` | object | a count per verdict name over every probe |
| `endpoints` | integer | how many endpoints the shift held |
| `probes` | integer | how many probes the shift held |
| `quarantined` | array | the sorted identifiers of the quarantined endpoints |
| `score_total` | integer | the sum of every endpoint's `score_total` |
| `top_endpoint` | string or null | the endpoint carrying the largest `score_total` |

How the `top_endpoint` tie is broken is a missing constant.

`endpoints.json` and `shift.json` are each
`json.dumps(document, sort_keys=True, indent=2)` followed by a newline.

## digest.json

A single JSON object carrying exactly these four keys.

| Key | Type | Content |
|---|---|---|
| `endpoints` | string | the digest of `endpoints.json` for the recorded shift |
| `precision` | string | the digest of `precision.csv` for the recorded shift |
| `shift` | string | the digest of `shift.json` for the recorded shift |
| `verdicts` | string | the digest of `verdicts.jsonl` for the recorded shift |

Every digest is the lowercase hexadecimal sha256 of a run of UTF-8 bytes, taken
over the exact bytes each report file holds as the serialization above produces
them. A digest matches only when every probe of the shift resolves correctly.

The file itself is `json.dumps(document, sort_keys=True, indent=2)` followed by
a newline.
