# Report layout

The program writes 23 reports into its output folder, with the names below, and one hold report for each household whose sweep ends with the exit `stalled`. Every text report is ASCII, ends each line with a single line feed, and ends with a line feed. Districts are taken in the order central, east, north, south, west wherever a report lists them, and the envelopes of one district in envelope code order.

JSON reports (the `.json` files) write objects with their keys in code point order, two spaces of indentation per level, a comma at the end of every item line except the last, a colon and one space between a key and its value, non-ASCII characters as `\u` escapes, and an empty list as `[]`. Numbers are integers.

## normalized.jsonl

One line per applied transaction, in code point order of the transaction id. Each line is a JSON object with no spaces, keys in code point order: `cents` (signed cents after corrections), `date`, `district`, `envelope` (the envelope code as the register of record writes it), `source` (the transaction export's file name) and `txn`.

## data_quality.json

`exports`: an object keyed by transaction export file name, each value an object with `rows` (data rows of that export), `malformed`, `out_of_period`, `applied` (rows that are applied transactions) and `voided` (well-formed rows of the period that a correction voided). `corrections`: an object with `applied` and `past_cutoff` (std_corrections.md).

## summary.json

`first_day`, `last_day` (from office.ini), `households` (5), `exits` (an object with keys `budget`, `cycling`, `settled`, `stalled`, each the number of households with that exit), `moved_dollars` (the sum of the households' moved dollars) and `transactions_applied` (the number of applied transactions).

## product_summary.json

`categories`: a list with one object per category that has at least one envelope, in code point order of the category name, each with `category`, `envelopes` (count), `presweep_dollars`, `final_dollars`, `moved_in_dollars` (sum over its envelopes of the amount by which the final balance exceeds the pre-sweep balance) and `moved_out_dollars` (sum of the amount by which the pre-sweep balance exceeds the final balance).

## region_central.json, region_east.json, region_north.json, region_south.json, region_west.json

One per district: `district`, `household` (household code), `family_name`, `exit`, `rounds`, `damping_percent`, `pool_dollars`, `moved_dollars`, and `envelopes`, a list with one object per envelope of the household holding `code`, `label`, `category`, `segment`, `need_dollars`, `presweep_dollars` and `final_dollars`.

## hold_<household code>.json

One per household whose sweep ends with the exit `stalled`, named `hold_` followed by the household code in lower case and `.json`; no hold report is written for any other household. It holds `district`, `household` (household code), `rounds`, `envelopes` (a list with one object per envelope of the household whose final balance is below its need, in envelope code order, holding `code`, `category`, `segment` and `short_dollars`, its need minus its final balance) and `short_dollars` (the sum of those envelopes' `short_dollars`).

## segment_consumer.json, segment_corporate.json, segment_enterprise.json, segment_smb.json

One per segment: `segment`, `envelopes` (count), `presweep_dollars`, `final_dollars`, and `members`, a list with one object per envelope of that segment holding `district`, `code` and `final_dollars`, by district and then envelope code.

## sweep_rounds.csv

Comma separated, header `district,round,spread,damping_percent,strikes,posted_dollars`, then one row per round run, by district and then round. `round` counts the rounds of the household from 1, `spread` is the spread of the round, `damping_percent` the damping rate of the round, `strikes` the strike count once the round's strike and any halving have been taken into account, and `posted_dollars` the sum of the round's positive posted amounts.

## envelope_final.tsv

Tab separated, with the header row `district`, `code`, `label`, `category`, `segment`, `final_dollars` joined by tabs, then one row per envelope with its values in that order.

## moves.csv

Comma separated, header `district,code,label,presweep_dollars,final_dollars,moved_dollars`, then one row per envelope whose final balance differs from its pre-sweep balance; `moved_dollars` is the final balance less the pre-sweep balance.

## exits.xml

The line `<?xml version="1.0" encoding="UTF-8"?>`, the line `<sweep>`, one line per household of the form `  <household district="..." exit="..." rounds="..." damping_percent="..." family_name="..."/>` with two leading spaces and the attributes in that order, and the line `</sweep>`. Attribute values write `&`, `<`, `>` and `"` as `&amp;`, `&lt;`, `&gt;` and `&quot;`.

## prior_delta.yaml

One line per district, `<district>: <n>`, where n is the household's moved dollars less the moved dollars prior_sweep.json gives for it, written as an integer with a leading minus sign when negative.

## reconciliation.txt

One line per district, `<district> pool=<pool dollars> final=<sum of final balances> moved=<moved dollars>`.

## ledger_totals.psv

Pipe separated, header `district|code|applied_cents|presweep_dollars`, then one row per envelope: the signed sum in cents of its applied transactions after corrections, and its pre-sweep balance.

## sweep.sqlite, sweep_book.xlsx, manifest.json

Laid out in layout_tables.md.
