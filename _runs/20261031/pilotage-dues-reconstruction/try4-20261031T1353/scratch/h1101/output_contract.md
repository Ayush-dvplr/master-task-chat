# Output contract

## Records

A record is one invoice row: a data line of a paid invoice file (tariff_circular.md
section 7) or of `disputed_batch.csv` (header `invoice_id,visit_id,station,invoice_date,billed`).
Lines are numbered from 1 in their file, header and wrapper lines included.

## Rejected records

A record is rejected with the first code of this list that applies to it:

1. `malformed_record`: a field of its layout is missing, its date is not a calendar date
   written `YYYY-MM-DD`, or its amount (`billed` in the disputed batch) is not euros
   written with digits, a point and two decimals.
2. `duplicate_invoice`: its `invoice_id` is on another record that is not malformed, in
   the same group of files. The four paid invoice files are one group and
   `disputed_batch.csv` is another. Every such record is rejected.
3. `unknown_visit`: its visit is not known (tariff_circular.md section 1).
4. `station_mismatch`: its visit's station is not the station of its paid file, or not the
   `station` of its disputed row.

A rejected paid record is not a record of any convention or tariff. A rejected disputed
record gets no verdict and is counted in no total.

## Fatal inputs

When a data file listed in `rule_register.md` is missing, or cannot be read in its layout
(a JSON file that does not parse, a CSV header that differs from its layout, an XML file
whose first or last line differs from its layout), the program writes
`ERROR unreadable input: <file name>` to standard error, writes no output document and
exits with status 2.

## Values

Money is a JSON string in euros with two decimals and a leading `-` when negative.
`difference` is billed minus recomputed. Totals are sums over accepted disputed records.
Tariff coefficients are JSON strings written as in tariff_circular.md section 3. Stations
are ordered North, South, West, East. Documents are compared as JSON values.

## Output documents

- `summary.json`: `disputes` (accepted disputed records), `verdict_counts` (an object with
  the four verdicts of tariff_circular.md section 6 as keys), `billed_total`,
  `recomputed_total` (over records with a recomputed due), `refund_total`,
  `shortfall_total`, `unresolved` (a list of `{station, period_start}` for every unresolved
  period, by station then period_start) and `largest_refund` (`{invoice_id, amount}` of the
  largest refund, the lower `invoice_id` on a tie, or null when there is no refund).
- `policy_audit.json`: `rows`, one per accepted disputed record, sorted by `invoice_id`,
  each with `invoice_id`, `visit_id`, `station`, `period_start`, `segment`, `billed`,
  `recomputed`, `difference`, `verdict` and `reason`. `recomputed` and `difference` are null
  and `reason` is the reason of section 6 when the verdict is `cannot_recompute`; `reason`
  is null otherwise.
- `data_quality.json`: `rejected`, a list of `{file, line, code}` sorted by file name then
  line, and `counts`, an object with each of the four codes as a key.
- `region_<station>.json`, one per station (`region_North.json` and so on): `station`,
  `periods` (a list in date order of `{period_start, tariff, reason, paid_invoices}`, where
  `tariff` is an object with the four coefficients of section 3 or null when the period is
  unresolved, `reason` is null or the reason of section 6, and `paid_invoices` counts the
  accepted paid records of the period), `disputes`, `verdict_counts`, `refund_total` and
  `shortfall_total`, over the station's accepted disputed records.
- `segment_<segment>.json`, for `commercial` and `public`: `segment`, `disputes`,
  `vessels` (distinct vessels among those records), `verdict_counts`, `billed_total`,
  `recomputed_total`, `refund_total` and `shortfall_total`, over the segment's accepted
  disputed records.
