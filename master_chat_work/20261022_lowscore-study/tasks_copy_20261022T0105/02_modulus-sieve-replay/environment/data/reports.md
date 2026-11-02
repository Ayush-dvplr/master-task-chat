# The four reports

The mill writes four files into its output directory. Two of them survive for
the recorded pass: `ref_forms.csv` and `ref_sieve.json` in this directory are the
per form rollup and the sieve rollup under their reference names. Neither the per
sample residue ledger nor the per lane rollup for that pass was kept, so nothing
here shows the resolved figures of any single sample or any single lane.

## residues.jsonl

One JSON object per line, one line per sample, in ascending `seq`. Every object
carries exactly these ten keys.

| Key | Type | Content |
|---|---|---|
| `action` | string | the sample's action, copied through |
| `analyst` | string | the sample's analyst, copied through |
| `band` | string | `peak`, `high`, `base` or `idle` |
| `drift_before` | integer | the lane's drift at the moment the sample resolved |
| `form` | string | the form named by the sample's lane, copied through |
| `lane` | string | the sample's lane, copied through |
| `seq` | integer | the sample's sequence number, copied through |
| `status` | string | `setup`, `voided`, `refused`, `flagged` or `kept` |
| `tag` | string | the sample's tag, copied through |
| `weight` | integer | the figure the chain settled on for this sample |

Each line is `json.dumps(record, sort_keys=True, separators=(",", ":"))` followed
by a newline.

## lanes.json

A single JSON object with one key, `lanes`, holding the list of per lane rows
sorted by `lane`. Every row carries exactly these thirteen keys.

| Key | Type | Content |
|---|---|---|
| `bands` | object | counts of `base`, `high`, `idle` and `peak` over the lane's samples |
| `credit_end` | integer | the lane's credit after its last sample |
| `drift_end` | integer | the lane's drift after its last sample |
| `faults` | integer | the lane's fault count after its last sample |
| `flagged` | integer | how many of the lane's samples resolved to `flagged` |
| `floor_end` | integer | the lane's floor after its last sample |
| `lane` | string | the lane identifier |
| `peak_weight` | integer | the largest `weight` among the lane's counted samples, or zero |
| `samples` | integer | how many samples the lane has |
| `sieved` | integer | how many of the lane's samples carry the `sieve` action |
| `top_tag` | string or null | the tag of the counted sample carrying the largest `weight`, or null when the lane has no counted sample |
| `verdict` | string | `sealed`, `held` or `cleared` |
| `weight_total` | integer | the sum of `weight` over the lane's counted samples |

A lane's counted samples are the ones whose `status` sits in the set the mill
counts. Which statuses those are is one of the missing constants.

When two counted samples on a lane carry the same `weight`, the one with the
lowest `seq` wins, so `top_tag` names the tag of the earliest of them.

The `verdict` ladder is ordered: the sealing test is applied first, the holding
test second, and `cleared` is what is left. The sealing figure is a missing
constant. A lane that is not sealed is `held` when its `drift_end` is above 51,
that is 52 or more.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## forms.csv

A comma separated table with the header line
`form,lanes,samples,weight_total,flagged` and one row per form that any residue
line names. No field is ever quoted and no field ever holds a comma.

| Column | Content |
|---|---|
| `form` | the form identifier |
| `lanes` | how many distinct lanes name this form |
| `samples` | how many residue lines name this form |
| `weight_total` | the sum of `weight` over this form's counted residue lines |
| `flagged` | how many of this form's residue lines resolved to `flagged` |

The rows are not in the order the identifiers sort in. One fixed ordering rule
decides the order, with one fixed tie break for rows the rule cannot separate.
Both are missing constants. The file ends with a newline.

## sieve.json

A single JSON object carrying exactly these eight keys.

| Key | Type | Content |
|---|---|---|
| `by_band` | object | counts of `base`, `high`, `idle` and `peak` over every sample in the pass |
| `by_status` | object | counts of `flagged`, `kept`, `refused`, `setup` and `voided` over every sample in the pass |
| `forms` | integer | how many rows `forms.csv` carries |
| `lanes` | integer | how many lanes the pass has |
| `samples` | integer | how many samples the pass has |
| `sealed` | array | the sorted identifiers of the lanes whose verdict is `sealed` |
| `top_lane` | string or null | the lane carrying the largest `weight_total`, or null on an empty pass |
| `weight_total` | integer | the sum of `weight_total` over every lane |

When two lanes carry the same largest `weight_total`, one fixed tie break decides
which lane `top_lane` names.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## The empty pass

A pass holding no lane and no sample still produces all four files.
`residues.jsonl` is empty, `lanes.json` carries an empty `lanes` list,
`forms.csv` carries its header line and nothing else, and `sieve.json` carries
every count at zero, an empty `sealed` list and a null `top_lane`.
