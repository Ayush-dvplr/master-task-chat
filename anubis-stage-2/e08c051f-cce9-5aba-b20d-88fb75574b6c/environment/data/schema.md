# FY28 collateral-gated settlement ladder: the written contract

This directory is a flat export of one fiscal year of settlement activity from a
wholesale distributor. It holds four event files, eight reference files, one
policy file, and this contract. There is no code.

No single file settles an event. Every event reaches its region, its currency,
its rate, its fiscal period and its channel only through a chain that crosses
several reference files, and whether an event is accepted at all depends on the
state of its counterparty's ladder at the moment the event lands. Row order in
an input file is never significant except in the two places this contract names
file order as the tie-break.

Every field value is trimmed of leading and trailing whitespace before it is
used. Identifiers (`event_id`, `counterparty_id`, `sku`, `warehouse`,
`postal_prefix`, `rate_date`, `sale_event_id`) are then compared exactly.
Terminal ids and all enumerated labels (`segment`, `region`, `category`,
`channel_group`, `kind`, `currency`) are compared after trimming and case
folding, and are emitted case folded: lower case for every label, upper case for
`currency`.

## Event files

- `sales.csv`, comma delimited:
  `event_id,trade_ts,counterparty_id,sku,warehouse,quantity,unit_price,currency,terminal`.
  Kind `sale`. The gross amount is `quantity * unit_price`, always positive.
- `refunds.tsv`, tab delimited:
  `event_id,trade_ts,counterparty_id,sku,warehouse,quantity,refund_amount,currency,terminal,sale_event_id`.
  Kind `refund`. The gross amount is minus the absolute value of
  `refund_amount`, whatever sign the column carries.
- `adjustments.jsonl`, one JSON object per line with the keys
  `event_id`, `trade_ts`, `counterparty_id`, `sku`, `kind`, `amount_minor`,
  `currency` and an optional `note`. `kind` is `fee` or `credit` in any letter
  case. `amount_minor` must be a JSON integer and carries its own sign; the
  gross amount is `amount_minor` divided by 100. An adjustment has no warehouse
  and no terminal, and its quantity is `0`.
- `legacy.txt`, pipe delimited, encoded latin-1. Blank lines and lines whose
  first non-blank character is `#` carry no event. Every other line has exactly
  eleven fields:
  `event_id|trade_ts|counterparty_id|sku|warehouse|kind|quantity|amount|currency|terminal|memo`.
  `amount` is the line total and is unsigned in practice; `sale` and `fee` take
  `+abs(amount)`, `refund` and `credit` take `-abs(amount)`, and any other kind
  token is malformed. `memo` is informational and may be empty.

`quantity` is an integer written with ASCII digits and nothing else. A value
carrying a sign, a decimal point, a word, a digit from another script, or
nothing at all is malformed. `quantity` may be `0`: such an event contributes
its full money and no units.

`trade_ts` is written `YYYY-MM-DDTHH:MM:SS`. In `sales.csv`, `refunds.tsv` and
`legacy.txt` it is local wall-clock time at the shipping warehouse. In
`adjustments.jsonl` it carries a trailing `Z` and is already UTC.

## Reference files

- `counterparties.csv`:
  `counterparty_id,name,segment,postal_code,opening_balance_minor,opening_currency,updated_at`.
  `segment` is one of `consumer`, `smb`, `corporate`, `enterprise`.
  `opening_balance_minor` is a signed integer in the minor units of
  `opening_currency`. A `counterparty_id` may appear on several rows; the row
  with the greatest `updated_at` is the one that counts, and when two rows share
  the greatest `updated_at` the later of them in file order counts.
- `regions.csv`: `postal_prefix,region,parent_region,manager,default_currency`.
  A postal code is written `<prefix>-<suffix>`; the text before the first `-` is
  the `postal_prefix`. `parent_region` is empty on a top level region and
  otherwise names the region one level up. The five top level regions are
  `central`, `east`, `north`, `south` and `west`. A record's reporting region is
  the top level ancestor of the region its postal prefix names.
  `default_currency` belongs to the matched prefix row. `manager` is
  informational.
- `inventory.csv`:
  `sku,warehouse,postal_code,tz_offset_minutes,on_hand_grams,reorder_point_grams`,
  one row per stocking pair, so a sku stocked in four warehouses appears four
  times. Every row for a warehouse repeats that warehouse's `postal_code` and
  `tz_offset_minutes`. A warehouse is known when it appears on any row. Stock
  figures are summed over every row for a sku.
- `channels.csv`: `terminal,channel_group,device`. Maps the terminal that booked
  the event to its `channel_group`. `device` is informational.
- `product_catalog.csv`: `sku,name,category,unit_mass_kg,active`. Gives the
  sku's `category` and its unit mass in kilograms. A sku counts whether or not
  it is `active`.
- `fx_rates.csv`: `rate_date,currency,usd_rate`, at most one row per currency
  per day, USD listed at 1. The rate that applies to a settlement date is the
  row for that currency on that exact date; when that date has no row for the
  currency, the row for that currency on the most recent earlier date applies.
- `fiscal_calendar.json`: a `periods` array of `period`, `start`, `end` and
  `weeks`. A settlement date belongs to the period whose closed `start` to `end`
  span contains it. Periods do not follow calendar months and do not cover the
  whole year; a date no period covers takes the `unassigned_period` label from
  `policy.ini`, which is not an error.
- `corrections.log`: one line per log entry, written
  `<utc_ts> <level> <message...>`. A line whose message begins with the word
  `correction` carries the tokens `target=<event_id>`, `field=<name>` and
  `value=<text>`, and replaces the named field of the named event with that
  text before any parsing of that event happens. `value` may be empty, which
  sets the field to the empty string. Any other line is informational. When
  several corrections name the same event and the same field, the one with the
  greatest `<utc_ts>` wins, and when two of them share the greatest `<utc_ts>`
  the later of them in file order wins. A correction whose `field` is not a
  column of its target's own event file is ignored, and so is one naming
  `event_id`, which identifies the event and is never replaced. A correction
  whose `target` matches no event id in any event file is unmatched and is
  reported.

## policy.ini

`policy.ini` carries the contract constants: the per segment collateral floors
in USD cents under `[collateral]`, the `opening_rate_date` under `[ladder]`, the
money and mass rounding mode under `[rounding]`, `grams_per_kilogram` under
`[mass]`, and the `unassigned_period` and `adjustment_channel_group` labels
under `[labels]`. Read them from the file; they are not repeated here.

## Settling one event

1. Apply every correction that names this event and a column of its own event
   file.
2. The counterparty comes from `counterparties.csv` and gives the `segment` and,
   for adjustments only, the postal code.
3. The postal code of a sale, refund or legacy event is its shipping
   warehouse's postal code from `inventory.csv`. The postal code of an
   adjustment is its counterparty's own.
4. The reporting `region` is the top level ancestor of the region that
   `regions.csv` gives for that postal code's prefix.
5. `currency` is the event's own currency when it has one, and otherwise the
   `default_currency` of the prefix row matched in step 4.
6. The UTC instant of a sale, refund or legacy event is its local `trade_ts`
   shifted by its warehouse's `tz_offset_minutes`, which may be negative. An
   adjustment's `trade_ts` is already UTC. The `settlement_date` is the calendar
   date of the UTC instant, and the fiscal period follows from that date.
   `trade_ts` must name a real calendar day; a day that does not exist is
   malformed.
7. The USD rate follows from `settlement_date` and `currency` under the rule in
   `fx_rates.csv` above. An event whose currency has no row on or before its
   settlement date is malformed.
8. `channel_group` comes from the event's terminal in `channels.csv`. An
   adjustment takes the `adjustment_channel_group` label from `policy.ini`.
9. `category` comes from the event's sku in `product_catalog.csv`.
10. `settled_usd_cents` is the gross amount multiplied by the USD rate and by
    100, built as one exact decimal expression and quantized exactly once, at
    that point and nowhere earlier, to a whole cent under the `[rounding]` mode
    in `policy.ini`.

## Malformed events

An event is malformed when any field it needs fails to parse under the rules
above, or when any lookup in the chain misses: an unknown counterparty, sku,
warehouse, terminal or postal prefix, a day that does not exist, a currency with
no usable rate, a legacy line without exactly eleven fields, an `amount_minor`
that is not a JSON integer, or an adjustment kind that is neither `fee` nor
`credit`. A malformed event is skipped, is counted against its own event file,
and appears in nothing else. An empty `note`, `memo`, `device` or `manager` is
normal and never a reason to skip.

## Orphan debit links

A refund whose `sale_event_id` is non-empty after trimming, and which does not
equal the `event_id` of any row present in `sales.csv`, is an orphan. Presence
in `sales.csv` is judged on the rows of that file as they stand, with no regard
for whether the sale itself settled. An orphan is reported by id, is excluded
from every total and never reaches the ladder. A `sale_event_id` that is empty
after trimming is not a link at all and the refund is ordinary.

This test reads the corrected `sale_event_id` and nothing else, and it runs
before any other field of the refund is parsed. A refund the test names is
therefore an orphan and not a malformed event, even where another of its fields
would have failed to parse: it is reported among the orphan ids and is counted
in no file's skipped tally. Orphan wins over malformed every time the two would
both apply.

## The collateral ladder

Each counterparty keeps one running balance in USD cents. It opens at
`opening_balance_minor` divided by 100, converted to USD cents by the rule in
step 10 using the rate for `opening_currency` on the `opening_rate_date` from
`policy.ini`.

The counterparty's events are then taken one at a time in order of UTC instant,
with `event_id` compared as text breaking a shared instant. Malformed events and
orphans are gone before this point and take no part.

An event whose `settled_usd_cents` is zero or positive is accepted and raises
the balance by that amount. An event whose `settled_usd_cents` is negative is
accepted only when the balance it would leave behind is at or above the
`[collateral]` floor for that counterparty's segment; when it would leave the
balance below that floor the event is collateral blocked, the balance does not
move, and the event is reported by id, kept out of `normalized.jsonl` and out of
every money total, and counted against its own event file and its own region and
segment. A blocked event does not end the ladder: later events on the same
counterparty are judged against the balance that the block left standing.

A counterparty whose opening balance is already below its segment floor is not
an error and blocks nothing by itself.

## The canonical settlement record

One JSON object per accepted event with exactly these sixteen keys:
`event_id`, `settlement_date`, `utc_instant`, `fiscal_period`,
`counterparty_id`, `segment`, `region`, `sku`, `category`, `kind`, `quantity`,
`settled_usd_cents`, `currency`, `source`, `channel_group`, `warehouse`.

- `utc_instant` is written `YYYY-MM-DDTHH:MM:SSZ` and `settlement_date`
  `YYYY-MM-DD`.
- `quantity` is the integer quantity, `0` for adjustments.
- `source` is the event file the row came from, extension included:
  `sales.csv`, `refunds.tsv`, `adjustments.jsonl` or `legacy.txt`.
- `warehouse` is the event's warehouse id, and `null` for an adjustment.
- Net units count a `sale` as `+quantity`, a `refund` as `-quantity`, and every
  other kind as zero, whatever money the event carries.

## Serialization

`normalized.jsonl` holds one accepted record per line, ordered by `event_id`
compared as text, each line a compact JSON object with sorted keys, no spaces
after the separators, and a trailing newline on every line. Every `.json`
artifact is a JSON document with sorted keys, a two space indent, and a closing
newline.

For the avoidance of doubt about the two serializations, a two key object is
written `{"a":1,"b":2}` on a `normalized.jsonl` line and

```json
{
  "a": 1,
  "b": 2
}
```

in a `.json` artifact.

## Aggregate artifacts

Money figures are sums of `settled_usd_cents` over accepted records. Every map
is emitted with sorted keys. An artifact is right only when every value in it is
right.

`summary.json`:
`event_count`, `skipped_count`, `blocked_count`, `orphan_refund_count`,
`total_usd_cents`, `net_units`, `ladder_closing_usd_cents`, and the breakdown
maps `by_region`, `by_segment`, `by_kind`, `by_category`, `by_channel_group`,
`by_fiscal_period` and `by_source`, each mapping a value that occurs among the
accepted records to its summed USD cents. `ladder_closing_usd_cents` is the sum
of every counterparty's closing balance over every counterparty
`counterparties.csv` names, including those with no events at all.

`data_quality.json`:
`input_files` (the name of every regular file in the input directory, sorted),
`records_by_source` (each `source` that produced at least one accepted record
mapped to that count), `skipped_by_source` and `blocked_by_source` (each of the
four event files present in the input directory mapped to its count, zeros
included), `skipped_count`, `blocked_count`, `orphan_refund_count`,
`blocked_event_ids`, `orphan_refund_event_ids` and
`unmatched_correction_targets`, the last three sorted and free of duplicates.

`product_summary.json`: a `products` array with one entry per sku in
`product_catalog.csv`, ordered by sku, including skus no event touched. Each
entry carries `sku`, `category`, `event_count`, `total_usd_cents`, `net_units`,
`on_hand_grams`, `reorder_point_grams` and `net_mass_grams`, where the two stock
figures are the sums over that sku's `inventory.csv` rows and `net_mass_grams`
is net units multiplied by `unit_mass_kg` and by `grams_per_kilogram`, built as
one exact decimal expression and quantized exactly once to a whole gram under
the `[rounding]` mode.

`region_central.json`, `region_east.json`, `region_north.json`,
`region_south.json` and `region_west.json`: one file per top level region, all
five written every run even when a region drew nothing. Keys: `region`,
`event_count`, `total_usd_cents`, `net_units`, `blocked_count`,
`counterparties` (the sorted distinct ids that contributed an accepted record),
`by_kind` and `by_category`.

`segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json`
and `segment_smb.json`: one file per segment, all four written every run. The
same keys with `segment` in place of `region`, plus
`collateral_floor_usd_cents`, that segment's floor from `policy.ini`.

## The closing report

The transform writes files; the closing message carries nine figures that no
artifact holds. Each is counted over the whole corpus the run was pointed at:

1. `blocked_value_usd_cents`: the sum of `settled_usd_cents` over every
   collateral blocked event.
2. `blocked_counterparties`: how many distinct counterparties had at least one
   collateral blocked event.
3. `carry_forward_rate_events`: how many accepted events took their rate from an
   earlier date because their settlement date had no row for their currency.
4. `day_shift_events`: how many accepted events have a `settlement_date` that
   differs from the calendar date written in their own `trade_ts`.
5. `corrected_events`: how many distinct event ids had at least one correction
   applied to them.
6. `half_cent_events`: how many accepted events had a money product whose
   fractional part was exactly half a cent before quantizing.
7. `underwater_counterparties`: how many counterparties open below their own
   segment floor.
8. `uncatalogued_stock_grams`: the sum of `on_hand_grams` over every
   `inventory.csv` row whose sku is absent from `product_catalog.csv`.
9. `stale_link_refunds`: how many accepted refunds carry a `sale_event_id` that
   names a `sales.csv` row that was itself skipped as malformed.
