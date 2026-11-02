# The three reports

The engine writes three files into its output directory. The `example_a_out_` and
`example_b_out_` files in this directory are those three, for the two mode zero
intakes, under prefixed names.

## settlements.jsonl

One JSON object per line, one line per resolved ticket, in the order the engine
resolved them. Every object carries exactly these nine keys.

| Key | Type | Content |
|---|---|---|
| `action` | string | the ticket's action, copied through |
| `band` | string | `prime`, `mill`, `feed` or `scrap` |
| `bin` | string | the ticket's bin, copied through |
| `bushels` | integer | the figure the chain produced for this ticket |
| `card` | string | the ticket's scale card, copied through |
| `dockage_before` | integer | the bin's dockage at the moment the ticket resolved |
| `grader` | string | the ticket's grader, copied through |
| `seq` | integer | the ticket's sequence number, copied through |
| `status` | string | `open`, `voided`, `rejected`, `flagged` or `clear` |

Each line is `json.dumps(record, sort_keys=True, separators=(",", ":"))` followed
by a newline.

## binroll.json

A single JSON object with one key, `bins`, holding the list of per bin rows
sorted by `bin`. Every row carries exactly these twelve keys.

| Key | Type | Content |
|---|---|---|
| `bands` | object | counts of `feed`, `mill`, `prime` and `scrap` over the bin's resolved tickets |
| `bin` | string | the bin identifier |
| `bushel_total` | integer | the sum of `bushels` over the bin's counted tickets |
| `disposition` | string | `embargo`, `hold` or `release` |
| `dockage_end` | integer | the bin's dockage after its last resolved ticket |
| `flagged` | integer | how many of the bin's resolved tickets landed on `flagged` |
| `peak` | integer | the largest `bushels` among the bin's counted tickets, or zero |
| `rejects` | integer | the bin's strike count after its last resolved ticket |
| `tare_end` | integer | the bin's tare level after its last resolved ticket |
| `tickets` | integer | how many of the bin's tickets were resolved |
| `top_card` | string or null | the card of the counted ticket carrying the largest `bushels`, or null when the bin has no counted ticket |
| `weighed` | integer | how many of the bin's resolved tickets carry the `weigh` action |

A bin's counted tickets are the ones whose `status` sits in the set the engine
counts. Which statuses those are is one of the missing constants.

When two counted tickets on a bin carry the same `bushels`, one fixed tie break
decides which card `top_card` names.

The `disposition` ladder is ordered: the embargo test is applied first, the hold
test second, and `release` is what is left.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## elevator.json

A single JSON object carrying exactly these eight keys.

| Key | Type | Content |
|---|---|---|
| `bins` | integer | how many bins the intake has |
| `bushel_total` | integer | the sum of `bushel_total` over every bin |
| `by_band` | object | counts of `feed`, `mill`, `prime` and `scrap` over every resolved ticket |
| `by_status` | object | counts of `clear`, `flagged`, `open`, `rejected` and `voided` over every resolved ticket |
| `embargoed` | array | the sorted identifiers of the bins whose disposition is `embargo` |
| `screened` | object | what intake screening did to `tickets.jsonl`: `conflicted`, the number of lines set aside in pass two because their `seq` is in conflict; `malformed`, the number of lines set aside as damaged in pass one; `reentered`, the number of lines set aside in pass three as re-entries of a claimed card; `retransmitted`, the number of copies past the first in the groups that resolved once |
| `tickets` | integer | how many tickets were resolved |
| `top_bin` | string or null | the bin carrying the largest `bushel_total`, or null on an empty intake |

When two bins carry the same largest `bushel_total`, one fixed tie break decides
which bin `top_bin` names.

The file is `json.dumps(document, sort_keys=True, indent=2)` followed by a
newline.

## The digests in manifest.json

Both digests are lowercase hex sha256 over UTF-8 text built from the three
reports above.

`bin_digests` maps each bin identifier to the digest of that bin alone. The text
digested is the bin's own lines of `settlements.jsonl`, in resolution order and
in the byte form given above, followed by that bin's row from `binroll.json`,
serialized on its own as `json.dumps(row, sort_keys=True, indent=2)` plus a
newline.

`run_digest` is the digest of the whole intake: the complete text of
`settlements.jsonl`, then the complete text of `binroll.json`, then the complete
text of `elevator.json`, concatenated in that order.

The two mode zero intakes let a digest routine be checked before it is trusted:
recompute both digests from the shipped `example_a_out_` files and they will
match `example_a_manifest.json`.
