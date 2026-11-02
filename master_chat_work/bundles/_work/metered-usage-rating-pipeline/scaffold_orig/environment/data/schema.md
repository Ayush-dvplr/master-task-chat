# Local commerce normalization schema

All files live directly in this flat directory. Build a deterministic stdlib-only
pipeline that normalizes local commerce transactions and aggregates them by fixed
regions and customer segments. No single file is enough: every transaction is
resolved through several reference files, and the chain below is the only way to
reach its region, currency, rate and channel.

Every field value is trimmed of surrounding whitespace before use. Identifiers
(`event_id`, `customer_id`, `sku`, `warehouse`, `terminal`, `postal_prefix`, dates)
are then compared exactly.

## Transaction inputs

- `sales.csv`: `event_id,date,customer_id,sku,warehouse,quantity,unit_price,currency,terminal`.
  Kind `sale`; the amount is `quantity * unit_price` in the row's currency.
- `refunds.csv`: `event_id,date,customer_id,sku,warehouse,quantity,refund_amount,currency,terminal,reason`.
  Kind `refund`; the amount is minus the absolute `refund_amount`.
- `adjustments.jsonl`: one JSON object per line with
  `event_id,date,customer_id,sku,kind,amount_cents,currency,note`. `kind` is `fee` or
  `credit` (any letter case). `amount_cents` must be a JSON integer; it is already
  signed, and `amount_cents / 100` is the amount. Adjustments have no warehouse and no
  terminal; their quantity is `0`.
- `legacy.txt`: blank lines and lines starting with `#` are ignored. Every other line
  has exactly eleven `|`-separated fields:
  `event_id|date|customer_id|sku|warehouse|kind|quantity|amount|currency|terminal|note`.
  `amount` is the row total. `sale` and `fee` count `+abs(amount)`; `refund` and
  `credit` count `-abs(amount)`. Kinds are matched in any letter case.

`quantity` must be a whole number written with digits only (`2`, not `2.0` or
`two`). Money columns are decimal strings.

## Reference inputs and how they chain

- `customers.csv`: `customer_id,name,segment,postal_code`. Gives the customer's
  `segment` and home `postal_code`.
- `regions.csv`: `postal_prefix,region,manager,default_currency`. A postal code is
  `<prefix>-<suffix>`; the part before the `-` is looked up as `postal_prefix` to
  get the canonical `region` and its `default_currency`. `manager` is informational.
- `inventory.csv`: `sku,warehouse,postal_code,on_hand,reorder_point`, one row per
  (sku, warehouse) stocking pair. Every row for a warehouse carries that
  warehouse's `postal_code`. A warehouse is known when it appears in any row.
- `channels.csv`: `terminal,channel_group,device`. Maps the terminal that took the
  transaction to its `channel_group`. `device` is informational.
- `product_catalog.csv`: `sku,name,category,unit_cost_usd,active`. Gives the SKU's
  `category`. A SKU is valid whether or not it is `active`.
- `fx_rates.csv`: `date,currency,usd_rate`, one row per day per currency (USD is
  listed at 1). The rate used is the row whose `date` and `currency` equal the
  transaction's.
- `calendar.csv`: `date,fiscal_week,is_holiday`. Gives the fiscal week of a date.
  `is_holiday` is informational. The calendar ends before the last transaction
  dates; a date it does not list has fiscal week `unknown` (that alone is not an
  error).

Resolution of one transaction:

1. `segment` comes from the customer.
2. The record's region comes from a postal code. For sales, refunds and legacy rows
   it is the shipping warehouse's postal code from `inventory.csv`. For adjustments
   it is the customer's home postal code.
3. `currency` is the row's currency, upper-cased. When the row's currency is empty,
   use the `default_currency` of the region found in step 2.
4. The USD rate is looked up by (date, currency) in `fx_rates.csv`.
5. `channel_group` comes from the terminal in `channels.csv`. Adjustments use the
   literal `adjustment`.

A transaction is malformed, and skipped, when any field it needs fails to parse, or
when any lookup in the chain fails: unknown customer, SKU, warehouse, terminal or
postal prefix, or no rate for its (date, currency). This includes impossible dates,
which have no rate. Do not skip a row only because a note or reason is empty.

## Canonical transaction record

Emit one JSON object per accepted transaction with exactly these keys:
`event_id`, `date`, `fiscal_week`, `customer_id`, `segment`, `region`, `sku`,
`category`, `kind`, `quantity`, `amount_usd_cents`, `currency`, `source`,
`channel_group`, `warehouse`.

- `segment`, `region`, `category`, `channel_group` and `kind` are lower-cased.
  `currency` is the resolved upper-case code from step 3.
- `quantity` is the integer quantity (`0` for adjustments).
- `source` is the input file the row came from, with its extension: `sales.csv`,
  `refunds.csv`, `adjustments.jsonl` or `legacy.txt`.
- `warehouse` is the row's warehouse id, or `null` for adjustments.
- `amount_usd_cents` is `amount * usd_rate * 100`, computed with `Decimal` and
  quantized to an integer with half-up rounding in one step.

Write `normalized.jsonl` as one compact JSON object per line (sorted keys, `,` and
`:` separators, no spaces), sorted by `event_id` compared as a string.

## Aggregate outputs

Every `.json` artifact is written with sorted keys and ends with a newline. The
aggregate figures are sums of `amount_usd_cents` over the matching records. Net
units count a `sale` as `+quantity`, a `refund` as `-quantity`, and every other kind
as zero.

`summary.json` carries `record_count`, `skipped_count`, `total_usd_cents`, and the
breakdown maps `by_region`, `by_segment`, `by_kind`, `by_category` and
`by_channel_group`, each mapping a value that occurs in the records to its summed
USD cents.

`data_quality.json` carries `input_files` (the names of every regular file in the
input directory, sorted), `records_by_source` (each `source` value mapped to its
accepted-record count, for sources that produced at least one record),
`skipped_by_source` (each of the four transaction files present in the input
directory mapped to its skipped-row count, `0` included) and `skipped_count` (the
total).

`product_summary.json` carries a `products` array with one entry per catalogue SKU,
sorted by SKU, including SKUs no transaction touched. Each entry has the keys `sku`,
`category`, `record_count`, `total_usd_cents`, `net_units`, `on_hand` and
`reorder_point`, where the two stock figures are summed over every `inventory.csv`
row for that SKU (0 when it has none).

Each `region_<name>.json` file has the keys `region` (the region name),
`record_count`, `total_usd_cents`, `net_units`, `customers` (the sorted distinct
customer ids that contributed), `by_kind` and `by_category`. Each
`segment_<name>.json` file has the same keys with `segment` in place of `region`.
Write all five region files (`central`, `east`, `north`, `south`, `west`) and all
four segment files (`consumer`, `corporate`, `enterprise`, `smb`) even when a bucket
drew no records.
