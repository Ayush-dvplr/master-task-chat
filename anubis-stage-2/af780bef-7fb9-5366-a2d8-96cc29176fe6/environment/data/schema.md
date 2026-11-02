# FY31 deposit-gated meter settlement: the written contract

This directory is a flat export of one fiscal year of metering activity from a
regional water and power retailer. It holds four event files, eight reference
files, one policy file, and this contract. There is no code.

No single file settles an event. Every event reaches its region, its currency,
its rate, its billing period and its channel only through a chain that crosses
several reference files, and whether an event is accepted at all depends on the
state of its account's deposit ladder at the moment the event lands. Row order
in an input file is never significant except in the two places this contract
names file order as the tie-break.

Every field value is trimmed of leading and trailing whitespace before it is
used. Identifiers (`event_id`, `account_id`, `tariff_code`, `substation`,
`postal_prefix`, `rate_date`, `read_event_id`) are then compared exactly.
Intake terminal ids and all enumerated labels (`segment`, `zone`, `category`,
`channel_group`, `kind`, `currency`) are compared after trimming and case
folding, and are emitted case folded: lower case for every label, upper case
for `currency`.

## Event files

- `meter_reads.csv`, comma delimited:
  `event_id,read_ts,account_id,tariff_code,substation,quantity,unit_rate,currency,intake_terminal`.
  Kind `charge`. The gross amount is `quantity * unit_rate`, always positive.
- `rebates.tsv`, tab delimited:
  `event_id,read_ts,account_id,tariff_code,substation,quantity,rebate_amount,currency,intake_terminal,read_event_id`.
  Kind `rebate`. The gross amount is minus the absolute value of
  `rebate_amount`, whatever sign the column carries.
- `adjustments.jsonl`, one JSON object per line with the keys
  `event_id`, `read_ts`, `account_id`, `tariff_code`, `kind`, `amount_minor`,
  `currency` and an optional `memo`. `kind` is `surcharge` or `waiver` in any
  letter case. `amount_minor` must be a JSON integer and carries its own sign;
  the gross amount is `amount_minor` divided by 100. An adjustment has no
  substation and no intake terminal, and its quantity is `0`.
- `legacy_ledger.txt`, pipe delimited, encoded latin-1. Blank lines and lines
  whose first non-blank character is `#` carry no event. Every other line has
  exactly eleven fields:
  `event_id|read_ts|account_id|tariff_code|substation|kind|quantity|amount|currency|intake_terminal|memo`.
  `amount` is the line total and is unsigned in practice; `charge` and
  `surcharge` take `+abs(amount)`, `rebate` and `waiver` take `-abs(amount)`,
  and any other kind token is malformed. `memo` is informational and may be
  empty.

`quantity` is an integer written with ASCII digits and nothing else. A value
carrying a sign, a decimal point, a word, a digit from another script, an inner
space, or nothing at all is malformed. `quantity` may be `0`: such an event
contributes its full money and no units.

`read_ts` is written `YYYY-MM-DDTHH:MM:SS`. In `meter_reads.csv`, `rebates.tsv`
and `legacy_ledger.txt` it is local wall-clock time at the reading substation.
In `adjustments.jsonl` it carries a trailing `Z` and is already UTC.

## Reference files

- `accounts.csv`:
  `account_id,name,segment,postal_code,opening_deposit_minor,opening_currency,updated_at`.
  `segment` is one of `consumer`, `smb`, `corporate`, `enterprise`.
  `opening_deposit_minor` is a signed integer in the minor units of
  `opening_currency`. An `account_id` may appear on several rows; the row with
  the greatest `updated_at` is the one that counts, and when two rows share the
  greatest `updated_at` the later of them in file order counts.
- `service_zones.csv`: `postal_prefix,zone,parent_zone,steward,default_currency`.
  A postal code is written `<prefix>-<suffix>`; the text before the first `-` is
  the `postal_prefix`. `parent_zone` is empty on a top level zone and otherwise
  names the zone one level up. The five top level zones are `central`, `east`,
  `north`, `south` and `west`, and the ladder of zones between a prefix and its
  top level zone may be more than one step long. A record's reporting region is
  the top level ancestor of the zone its postal prefix names.
  `default_currency` belongs to the matched prefix row. `steward` is
  informational.
- `meter_fleet.csv`:
  `tariff_code,substation,postal_code,tz_offset_minutes,metered_capacity_litres,service_threshold_litres`,
  one row per installed pair, so a tariff code metered at four substations
  appears four times. Every row for a substation repeats that substation's
  `postal_code` and `tz_offset_minutes`. A substation is known when it appears
  on any row. Capacity figures are summed over every row for a tariff code.
- `intake_channels.csv`: `intake_terminal,channel_group,device_class`. Maps the
  terminal that booked the event to its `channel_group`. `device_class` is
  informational.
- `tariff_catalogue.csv`: `tariff_code,label,category,unit_volume_m3,active`.
  Gives the tariff code's `category` and its unit volume in cubic metres. A
  tariff code counts whether or not it is `active`.
- `currency_rates.csv`: `rate_date,currency,usd_rate`, at most one row per
  currency per day, USD listed at 1. The rate that applies to a settlement date
  is the row for that currency on that exact date; when that date carries no row
  for the currency, the row for that currency on the nearest date before it
  applies.
- `billing_calendar.json`: a `cycles` array of `cycle`, `opens`, `closes` and
  `weeks`. A settlement date belongs to the cycle whose closed `opens` to
  `closes` span contains it. Cycles do not follow calendar months and do not
  cover the whole year; a date no cycle covers takes the `unassigned_cycle`
  label from `policy.ini`, which is not an error.
- `audit_trail.log`: one line per log entry, written
  `<utc_ts> <level> <message...>`. A line whose message begins with the word
  `amendment` carries the tokens `target=<event_id>`, `field=<name>` and
  `value=<text>`, and replaces the named field of the named event with that text
  before any parsing of that event happens. `value` may be empty, which sets the
  field to the empty string. Any other line is informational. When several
  amendments name the same event and the same field, the one with the greatest
  `<utc_ts>` wins, and when two of them share the greatest `<utc_ts>` the later
  of them in file order wins. An amendment whose `field` is not a column of its
  target's own event file is ignored, and so is one naming `event_id`, which
  identifies the event and is never replaced. An amendment whose `target`
  matches no event id in any event file is unmatched and is reported. A legacy
  line without exactly eleven fields carries no event id for this match, so an
  amendment naming it is unmatched, even though that line is still counted as a
  malformed event of its own file.

## policy.ini

`policy.ini` carries the contract constants: the per segment minimum deposits in
USD cents under `[deposit]`, the `opening_rate_date` and the `strike_limit`
under `[ladder]`, the money and volume rounding mode under `[rounding]`,
`litres_per_cubic_metre` under `[volume]`, and the `unassigned_cycle` and
`adjustment_channel_group` labels under `[labels]`. Read them from the file;
they are not repeated here.

## Settling one event

1. Apply every amendment that names this event and a column of its own event
   file.
2. The account comes from `accounts.csv` and gives the `segment` and, for
   adjustments only, the postal code.
3. The postal code of a meter read, rebate or legacy event is its reading
   substation's postal code from `meter_fleet.csv`. The postal code of an
   adjustment is its account's own.
4. The reporting `region` is the top level ancestor of the zone that
   `service_zones.csv` gives for that postal code's prefix.
5. `currency` is the event's own currency when it has one, and otherwise the
   `default_currency` of the prefix row matched in step 4.
6. The UTC instant of a meter read, rebate or legacy event is its local
   `read_ts` shifted by its substation's `tz_offset_minutes`, which may be
   negative. An adjustment's `read_ts` is already UTC. The `settlement_date` is
   the calendar date of the UTC instant, and the billing period follows from
   that date. `read_ts` must name a real calendar day; a day that does not exist
   is malformed.
7. The USD rate follows from `settlement_date` and `currency` under the rule in
   `currency_rates.csv` above. An event whose currency has no row on or before
   its settlement date is malformed.
8. `channel_group` comes from the event's intake terminal in
   `intake_channels.csv`. An adjustment takes the `adjustment_channel_group`
   label from `policy.ini`.
9. `category` comes from the event's tariff code in `tariff_catalogue.csv`.
10. `settled_usd_cents` is the gross amount multiplied by the USD rate and by
    100, built as one exact decimal expression and quantized exactly once, at
    that point and nowhere earlier, to a whole cent under the `[rounding]` mode
    in `policy.ini`.

## Malformed events

An event is malformed when any field it needs fails to parse under the rules
above, or when any lookup in the chain misses: an unknown account, tariff code,
substation, intake terminal or postal prefix, a day that does not exist, a
currency with no usable rate, a legacy line without exactly eleven fields, an
`amount_minor` that is not a JSON integer, or an adjustment kind that is neither
`surcharge` nor `waiver`. A malformed event is skipped, is counted against its
own event file, and appears in nothing else. An empty `memo`, `device_class` or
`steward` is normal and never a reason to skip.

## Orphan rebate links

A rebate whose `read_event_id` is non-empty after trimming, and which does not
equal the `event_id` of any row present in `meter_reads.csv`, is an orphan.
Presence in `meter_reads.csv` is judged on the rows of that file as they stand,
with no regard for whether the meter read itself settled. An orphan is reported
by id, is excluded from every total and never reaches the ladder. A
`read_event_id` that is empty after trimming is not a link at all and the rebate
is ordinary.

This test reads the amended `read_event_id` and nothing else, and it runs before
any other field of the rebate is parsed. A rebate the test names is therefore an
orphan and not a malformed event, even where another of its fields would have
failed to parse: it is reported among the orphan ids and is counted in no file's
skipped tally. Orphan wins over malformed every time the two would both apply.

## The deposit ladder

Each account keeps one running deposit balance in USD cents. It opens at
`opening_deposit_minor` divided by 100, converted to USD cents by the rule in
step 10 using the rate for `opening_currency` on the `opening_rate_date` from
`policy.ini`.

The account's events are then taken one at a time in order of UTC instant, with
`event_id` compared as text breaking a shared instant. Malformed events and
orphans are gone before this point and take no part. Each account also carries a
strike count that opens at zero and a service state that opens unsuspended.

An event whose `settled_usd_cents` is zero or positive is accepted and raises the
balance by that amount. An event whose `settled_usd_cents` is negative is
accepted only when the balance it would leave behind is at or above the
`[deposit]` minimum for that account's segment; it is then accepted and lowers
the balance by that amount.

When a negative event would leave the balance below that minimum it is withheld:
the balance does not move, the account's strike count rises by one, and the event
is gate blocked. A withheld event does not end the ladder by itself: later events
on the same account are judged against the balance that the withholding left
standing.

The strike that takes an account's count to the `strike_limit` from `policy.ini`
suspends the account. The event that drew that strike is itself withheld, and
every event of that account after it, positive or negative, is gate blocked as
suspended without moving the balance and without drawing a further strike. An
account that never reaches the limit is never suspended, and a suspension lasts
to the end of the book.

A gate blocked event, withheld or suspended, is reported by id, kept out of
`normalized.jsonl` and out of every money total, and counted against its own
event file and its own region and segment. An account whose opening balance is
already below its segment minimum is not an error and blocks nothing by itself.

## The canonical settlement record

One JSON object per accepted event with exactly these sixteen keys:
`event_id`, `settlement_date`, `utc_instant`, `billing_period`, `account_id`,
`segment`, `region`, `tariff_code`, `category`, `kind`, `quantity`,
`settled_usd_cents`, `currency`, `source`, `channel_group`, `substation`.

- `utc_instant` is written `YYYY-MM-DDTHH:MM:SSZ` and `settlement_date`
  `YYYY-MM-DD`.
- `quantity` is the integer quantity, `0` for adjustments.
- `source` is the event file the row came from, extension included:
  `meter_reads.csv`, `rebates.tsv`, `adjustments.jsonl` or `legacy_ledger.txt`.
- `substation` is the event's substation id, and `null` for an adjustment.
- Net units count a `charge` as `+quantity`, a `rebate` as `-quantity`, and
  every other kind as zero, whatever money the event carries.

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
`event_count`, `skipped_count`, `blocked_count`, `orphan_rebate_count`,
`total_usd_cents`, `net_units`, `deposit_closing_usd_cents`, and the breakdown
maps `by_region`, `by_segment`, `by_kind`, `by_category`, `by_channel_group`,
`by_billing_period` and `by_source`, each mapping a value that occurs among the
accepted records to its summed USD cents. `deposit_closing_usd_cents` is the sum
of every account's closing balance over every account `accounts.csv` names,
including those with no events at all.

`data_quality.json`:
`input_files` (the name of every regular file in the input directory, sorted),
`records_by_source` (each `source` that produced at least one accepted record
mapped to that count), `skipped_by_source` and `blocked_by_source` (each of the
four event files present in the input directory mapped to its count, zeros
included), `skipped_count`, `blocked_count`, `orphan_rebate_count`,
`blocked_event_ids`, `orphan_rebate_event_ids` and
`unmatched_amendment_targets`, the last three sorted and free of duplicates.

`product_summary.json`: a `tariffs` array with one entry per tariff code in
`tariff_catalogue.csv`, ordered by tariff code, including codes no event
touched. Each entry carries `tariff_code`, `category`, `event_count`,
`total_usd_cents`, `net_units`, `metered_capacity_litres`,
`service_threshold_litres` and `net_volume_litres`, where the two fleet figures
are the sums over that tariff code's `meter_fleet.csv` rows and
`net_volume_litres` is net units multiplied by `unit_volume_m3` and by
`litres_per_cubic_metre`, built as one exact decimal expression and quantized
exactly once to a whole litre under the `[rounding]` mode.

`region_central.json`, `region_east.json`, `region_north.json`,
`region_south.json` and `region_west.json`: one file per top level region, all
five written every run even when a region drew nothing. Keys: `region`,
`event_count`, `total_usd_cents`, `net_units`, `blocked_count`, `accounts` (the
sorted distinct ids that contributed an accepted record), `by_kind` and
`by_category`.

`segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json`
and `segment_smb.json`: one file per segment, all four written every run. The
same keys with `segment` in place of `region`, plus
`minimum_deposit_usd_cents`, that segment's minimum from `policy.ini`.

## The closing report

The transform writes files; the closing message carries thirteen figures that no
artifact holds. Each is counted over the whole corpus the run was pointed at:

1. `withheld_value_usd_cents`: the sum of `settled_usd_cents` over every
   withheld event, counting the events a suspension blocked in no part of it.
2. `suspended_accounts`: how many distinct accounts had at least one event gate
   blocked because the account stood suspended.
3. `carry_forward_rate_events`: how many accepted events took their rate from an
   earlier date because their settlement date had no row for their currency.
4. `day_shift_events`: how many accepted events have a `settlement_date` that
   differs from the calendar date written in their own `read_ts`.
5. `amended_events`: how many distinct event ids had at least one amendment
   applied to them.
6. `half_cent_events`: how many accepted events had a money product whose
   fractional part was exactly half a cent before quantizing.
7. `underfunded_accounts`: how many accounts open below their own segment
   minimum.
8. `unlisted_capacity_litres`: the sum of `metered_capacity_litres` over every
   `meter_fleet.csv` row whose tariff code is absent from
   `tariff_catalogue.csv`.
9. `stale_link_rebates`: how many accepted rebates carry a `read_event_id` that
   names a `meter_reads.csv` row that was itself skipped as malformed.
10. `withheld_event_count`: how many events the `withheld_value_usd_cents` sum
    covers, counting the events a suspension blocked in no part of it.
11. `gate_blocked_accounts`: how many distinct accounts had at least one event
    gate blocked, whether that event was withheld or blocked as suspended.
12. `carry_forward_rate_currencies`: how many distinct currencies appear among
    the accepted events that took their rate from an earlier date.
13. `half_cent_negative_events`: how many of the accepted events whose money
    product landed exactly on the half cent carried a negative product, which
    the `[rounding]` mode sends away from zero.
