# Output Contract: Disputed Pilotage Dues Review

## Records

- Line numbers count physical lines from 1, header lines included.
- Records are: BOARD, RELEASE and CANCEL lines of `pilot_movements.log`; data lines of
  `vessel_register.tsv`, `paid_north.csv` and `disputed_batch.csv`; lines of `paid_south.jsonl`; lines
  of `paid_west.txt`; `<invoice .../>` lines of `paid_east.xml`. Blank lines, header lines, NOTE lines
  and the first and last line of `paid_east.xml` are not records.

## Rejected records

Each record that is rejected gets exactly one code, the first that applies in this order:

1. `malformed_record`: the line does not follow the layout its governing file states for it.
2. `duplicate_invoice`: the invoice id appears on more than one record that is not malformed, counted
   across the four paid invoice files together, or within `disputed_batch.csv`. Every such record is
   rejected.
3. `unknown_visit`: an invoice whose visit id is not a known visit. A visit is known when it has an
   accepted BOARD line and an accepted RELEASE line, or an accepted CANCEL line, and its vessel has an
   accepted register line.
4. `station_mismatch`: a paid invoice in the file of a station other than the visit's station, or a
   disputed invoice whose `station` differs from the visit's station.
5. `early_invoice`: an invoice whose `invoice_date` is before the date of its visit's instant.
6. `already_paid`: a disputed invoice whose visit has an accepted paid invoice.

Lines of `pilot_movements.log` and `vessel_register.tsv` can only be rejected as `malformed_record`.
Rejected records are left out of every other computation.

## Superseded invoices

The `supersedes` field of `disputed_batch.csv` is empty or holds the id of a disputed invoice that the
line replaces. A disputed invoice named in the `supersedes` field of an accepted disputed invoice is
superseded: it gets no verdict and no row, and it is left out of every output document,
`data_quality.json` included. A rejected disputed record that carries the id of a superseded invoice
is left out of `data_quality.json` too, whatever its code.
Example on invented values: accepted lines `D0000001,...,` and `D0000002,...,D0000001` give one
verdict and one row, for D0000002.

## Fatal inputs

When a data file named in `rule_register.md` is missing, `holidays.json` or `certificates.json` is not
one JSON object, the header line of a CSV or TSV file differs from the header its governing file
states, or `paid_east.xml` lacks its stated first or last line, the program writes
`ERROR unreadable input: <file name>` to standard error and exits with status 2.

## Values

- Money is a JSON string with exactly two decimals, with a leading `-` when negative, for example
  `"1234.50"` and `"-0.40"`. Sums of money add the rounded amounts.
- Dates are `YYYY-MM-DD` strings. Counts and minutes are JSON integers. Missing values are `null`.
- Tariff coefficients are strings with two decimals, for example `"1.40"`.
- `verdict_counts` is an object with the four verdict names of `tariff_circular.md` section 6 as keys,
  each mapped to a count, zero included.
- Reasons are the strings of `tariff_circular.md` section 6.

## Output documents

The program writes these JSON documents into the output directory, creating it when needed.

`summary.json`: `disputes` (accepted disputed invoices), `verdict_counts`, `billed_total`,
`recomputed_total` (over invoices with a recomputed due), `refund_total` (over `overbilled`),
`shortfall_total` (over `underbilled`), and `largest_refund`: an object with the keys `invoice_id` and
`amount` for the `overbilled` invoice with the largest refund, the lower invoice id on a tie, or `null`
when there is none.

`policy_audit.json`: `rows`, one object per accepted disputed invoice, sorted by `invoice_id`, with the
keys `invoice_id`, `visit_id`, `station`, `period_start`, `segment`, `billed`, `recomputed`,
`difference` (billed minus recomputed), `verdict`, `reason`, `onboard_minutes`, `billed_minutes`.
`recomputed` and `difference` are `null` when there is no recomputed due.

`data_quality.json`: `rejected`, one object per rejected record with the keys `file` (file name),
`line`, `code`, sorted by file name and then line; and `counts`, an object with the six codes as keys,
each mapped to a count, zero included.

`region_<station>.json` for each of North, South, West and East: `station`; `periods`, one object per
period in start order with the keys `period_start`, `tariff` (the period's combination as an object
with the keys `base_per_100gt`, `draft_per_dm`, `night_factor`, `per_tug`, or `null`), `reason` (the
reason string of `tariff_circular.md` section 6 that applies to the period, or `null`) and
`paid_invoices` (accepted paid invoices of the period); `disputes`, `verdict_counts`, `refund_total`,
`shortfall_total` over the station's accepted disputed invoices.

`segment_<segment>.json` for each of commercial and public: `segment`, `disputes`, `vessels` (the number of
distinct vessel ids of the segment's accepted disputed invoices), `verdict_counts`, `billed_total`,
`recomputed_total`, `refund_total`, `shortfall_total` over the segment's accepted disputed invoices,
and `exempt_minutes`, the sum of on-board minutes minus billed minutes over them.
