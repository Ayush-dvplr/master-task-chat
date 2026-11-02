# Output schema

## Program

The program is run as

    python3 /app/out/transform.py --data <data directory> --out <output directory>

with absolute paths, from any working directory. It reads every input from
the data directory, by the paths given in `docs/RULES.md` and in
`ref/processors.json`, and writes every output document into the output
directory, creating it when it does not exist. It uses only the Python 3
standard library. The same input gives byte-identical output on every run.

If a declared input file is missing or cannot be parsed, the program exits
with a non-zero status and writes a message on standard error that names the
file by its path relative to the data directory, for example
`exports/lumen_settlement.txt`.

## Value forms

- Litres and tier volumes are strings with exactly 3 decimal places; money
  amounts are strings with exactly 2 decimal places. A zero value is written
  without a sign (`0.000`, `0.00`); a negative value starts with `-`.
- Dates are strings `YYYY-MM-DD`. Counts are JSON integers. `capped` is a JSON
  boolean.
- Every `.json` document is written with `json.dumps(document, indent=2,
  sort_keys=True)` followed by one newline.

## Check order and rejection reasons

Each line is checked in this order; the first check it fails gives its
reason.

| order | reason | applies to |
|---|---|---|
| 1 | `superseded_batch` or `withdrawn_batch` | every line |
| 2 | `pump_test` | every line |
| 3 | `void_record` | every line |
| 4 | `out_of_period` | every line |
| 5 | `unknown_product` | sale lines |
| 6 | `unknown_card` | sale lines |
| 7 | `account_closed` | sale lines |
| 8 | `voided` or `replaced` | every line |
| 9 | `duplicate` | every line |
| 10 | `orphan_reversal` or `ambiguous_reversal` | reversal lines |

A reversal line takes its product, card holder and account from the row it
reverses, so checks 5 to 7 do not apply to it.

## Ledger order

Ledger rows are ordered by business date, then by ledger id compared as
plain text. Lines that have not yet settled are put in ledger order the same
way, by their business date and the ledger id they would carry.

## normalized.jsonl

One ledger row per line, in ledger order, each written with
`json.dumps(row)` (default separators, keys in this order): `ledger_id`,
`processor`, `source_id`, `entry` (`sale` or `reversal`), `business_date`,
`account_id`, `segment`, `region`, `site_id`, `product` (catalogue code),
`kind`, `litres`, `net_amount`, `tax_amount`, `discount_amount`,
`settled_amount`, `tier` (a tier name or `none`). The file ends with a
newline.

## Totals block

Several documents use a totals block: an object with `lines` (number of
ledger rows), `litres`, `net_amount`, `tax_amount`, `discount_amount` and
`settled_amount`, each the sum over the ledger rows it covers.

## summary.json

- `month`: the settlement month.
- `ledger_rows`: the number of ledger rows.
- `totals`: totals block over all ledger rows.
- `accounts`: one object per account with at least one ledger row, ordered by
  `account_id`, with `account_id`, `segment` (in force on the last day of the
  month), `tier_volume`, `tier` (the tier earned by the tier volume, whatever
  the segment), `discount_amount` (sum over the account's rows) and `capped`
  (true when the cap reduced the discount of at least one of its sale rows).

## data_quality.json

- `month`: the settlement month.
- `processors`: one key per processor, each an object with `rows_read`,
  `rows_settled` and `rows_rejected`.
- `rejected`: one object per rejected line with `processor`, `source_id` and
  `reason`, ordered by processor, then source id, then reason, each compared
  as plain text.
- `reason_counts`: one key per reason in the table above, each the number of
  lines rejected with it (0 when none).

The source id of a rejected line is the one its processor handbook defines,
even when the line is rejected before it is read further.

## product_summary.json

- `month`: the settlement month.
- `products`: one key per catalogue product code, each a totals block over the
  product's ledger rows with an added `kind`.

## region_<region>.json

One document for each of `central`, `east`, `north`, `south` and `west`:

- `month`, `region`;
- `totals`: totals block over the region's ledger rows;
- `by_processor`: one key per processor, each a totals block over the
  region's ledger rows from that processor.

## segment_<segment>.json

One document for each of `consumer`, `corporate`, `enterprise` and `smb`:

- `month`, `segment`;
- `totals`: totals block over the ledger rows with that segment;
- `by_tier`: one key per tier in `ref/discount_tiers.ini` and one key `none`,
  each a totals block over those rows with that tier.
