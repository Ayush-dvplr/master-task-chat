# BY41 prepay-gated meter posting run: the written contract

This directory is a flat export of one billing year of metering activity from a
regional water and power utility. It holds four reading files, eight reference
files, one policy file, and this contract. There is no code.

No single file posts a reading. Every reading reaches its zone, its currency,
its rate, its billing cycle and its route group only through a chain that
crosses several reference files, and whether a reading posts at all depends on
the state of its account's prepay wallet at the moment the reading lands. Row
order in an input file is never significant except in the two places this
contract names file order as the tie-break.

Every field value is trimmed of leading and trailing whitespace before it is
used. Identifiers (`reading_id`, `account_id`, `tariff_code`, `meter_site`,
`postcode_prefix`, `rate_date`, `charge_reading_id`) are then compared exactly.
Collector ids and all enumerated labels (`tariff_class`, `zone`, `category`,
`route_group`, `kind`, `currency`) are compared after trimming and case folding,
and are emitted case folded: lower case for every label, upper case for
`currency`.

## Reading files

- `consumption.csv`, comma delimited:
  `reading_id,read_ts,account_id,tariff_code,meter_site,units_consumed,rate_per_unit,currency,collector`.
  Kind `consumption`. A consumption reading draws the wallet down, so its gross
  amount is minus `units_consumed * rate_per_unit` and is never positive.
- `remittances.tsv`, tab delimited:
  `reading_id,read_ts,account_id,tariff_code,meter_site,units_consumed,remit_amount,currency,collector,charge_reading_id`.
  Kind `remittance`. A remittance tops the wallet up, so its gross amount is
  plus the absolute value of `remit_amount`, whatever sign the column carries.
- `levies.jsonl`, one JSON object per line with the keys `reading_id`,
  `read_ts`, `account_id`, `tariff_code`, `kind`, `amount_minor`, `currency` and
  an optional `note`. `kind` is `surcharge` or `rebate` in any letter case.
  `amount_minor` must be a JSON integer and carries its own sign; the gross
  amount is `amount_minor` divided by 100, and the sign that reaches the wallet
  is the sign the column carries and not one implied by `kind`. A levy has no
  meter site and no collector, and its units are `0`.
- `legacy_reads.txt`, pipe delimited, encoded latin-1. Blank lines and lines
  whose first non-blank character is `#` carry no reading. Every other line has
  exactly eleven fields:
  `reading_id|read_ts|account_id|tariff_code|meter_site|kind|units_consumed|amount|currency|collector|memo`.
  `amount` is the line total and is unsigned in practice; `consumption` and
  `surcharge` take `-abs(amount)`, `remittance` and `rebate` take
  `+abs(amount)`, and any other kind token is malformed. `memo` is
  informational and may be empty.

`units_consumed` is an integer written with ASCII digits and nothing else. A
value carrying a sign, a decimal point, a word, a digit from another script, or
nothing at all is malformed. `units_consumed` may be `0`: such a reading
contributes its full money and no units.

`read_ts` is written `YYYY-MM-DDTHH:MM:SS`. In `consumption.csv`,
`remittances.tsv` and `legacy_reads.txt` it is local wall-clock time at the
meter site. In `levies.jsonl` it carries a trailing `Z` and is already UTC.

## Reference files

- `accounts.csv`:
  `account_id,holder,tariff_class,service_postcode,opening_credit_minor,opening_currency,revised_at`.
  `tariff_class` is one of `consumer`, `smb`, `corporate`, `enterprise`.
  `opening_credit_minor` is a signed integer in the minor units of
  `opening_currency`. An `account_id` may appear on several rows; the row with
  the greatest `revised_at` is the one that counts, and when two rows share the
  greatest `revised_at` the later of them in file order counts.
- `service_zones.csv`:
  `postcode_prefix,zone,parent_zone,inspector,default_currency`. A postcode is
  written `<prefix>-<suffix>`; the text before the first `-` is the
  `postcode_prefix`. `parent_zone` is empty on a top level zone and otherwise
  names the zone one level up. The five top level zones are `central`, `east`,
  `north`, `south` and `west`. A record's reporting zone is the top level
  ancestor of the zone its postcode prefix names. `default_currency` belongs to
  the matched prefix row. `inspector` is informational.
- `meter_sites.csv`:
  `tariff_code,meter_site,postcode,utc_offset_minutes,installed_litres,service_floor_litres`,
  one row per metering pair, so a tariff code metered at four sites appears four
  times. Every row for a meter site repeats that site's `postcode` and
  `utc_offset_minutes`. A meter site is known when it appears on any row.
  Capacity figures are summed over every row for a tariff code.
- `collectors.csv`: `collector,route_group,firmware`. Maps the collector that
  booked the reading to its `route_group`. `firmware` is informational.
- `tariff_catalogue.csv`:
  `tariff_code,label,category,unit_volume_litres,retired`. Gives the tariff
  code's `category` and its per unit volume in kilolitres. A tariff code counts
  whether or not it is `retired`.
- `currency_rates.csv`: `rate_date,currency,usd_rate`, at most one row per
  currency per day, USD listed at 1. The rate that applies to a posting date is
  the row for that currency on that exact date; when that date has no row for
  the currency, the row for that currency on the most recent earlier date
  applies. A later row is never reached backwards.
- `billing_calendar.json`: a `cycles` array of `cycle`, `opens`, `closes` and
  `weeks`. A posting date belongs to the cycle whose closed `opens` to `closes`
  span contains it. Cycles do not follow calendar months and do not cover the
  whole year; a date no cycle covers takes the `unassigned_cycle` label from
  `policy.ini`, which is not an error.
- `amendments.log`: one line per log entry, written
  `<utc_ts> <level> <message...>`. A line whose message begins with the word
  `amendment` carries the tokens `target=<reading_id>`, `field=<name>` and
  `value=<text>`, and replaces the named field of the named reading with that
  text before any parsing of that reading happens. `value` may be empty, which
  sets the field to the empty string. Any other line is informational. When
  several amendments name the same reading and the same field, the one with the
  greatest `<utc_ts>` wins, and when two of them share the greatest `<utc_ts>`
  the later of them in file order wins. An amendment whose `field` is not a
  column of its target's own reading file is ignored, and so is one naming
  `reading_id`, which identifies the reading and is never replaced. An
  amendment whose `target` matches no reading id in any reading file is
  unmatched and is reported. A line this contract calls malformed yields no
  reading at all, so an id that appears only on such a line matches nothing: an
  amendment naming it is unmatched and is reported, whatever its `field` says,
  and so is one naming `reading_id`.

## policy.ini

`policy.ini` carries the contract constants: the per class disconnection floors
in USD cents under `[disconnection]`, the `opening_rate_date` under `[wallet]`,
the money and volume rounding mode under `[rounding]`, `litres_per_kilolitre`
under `[volume]`, and the `unassigned_cycle` and `levy_route_group` labels under
`[labels]`. Read them from the file; they are not repeated here.

## Posting one reading

1. Apply every amendment that names this reading and a column of its own
   reading file.
2. The account comes from `accounts.csv` and gives the `tariff_class` and, for
   levies only, the postcode.
3. The postcode of a consumption, remittance or legacy reading is its meter
   site's postcode from `meter_sites.csv`. The postcode of a levy is its
   account's own.
4. The reporting `zone` is the top level ancestor of the zone that
   `service_zones.csv` gives for that postcode's prefix.
5. `currency` is the reading's own currency when it has one, and otherwise the
   `default_currency` of the prefix row matched in step 4.
6. The UTC instant of a consumption, remittance or legacy reading is its local
   `read_ts` shifted by its meter site's `utc_offset_minutes`, which may be
   negative. A levy's `read_ts` is already UTC. The `posting_date` is the
   calendar date of the UTC instant, and the billing cycle follows from that
   date. `read_ts` must name a real calendar day; a day that does not exist is
   malformed.
7. The USD rate follows from `posting_date` and `currency` under the rule in
   `currency_rates.csv` above. A reading whose currency has no row on or before
   its posting date is malformed.
8. `route_group` comes from the reading's collector in `collectors.csv`. A levy
   takes the `levy_route_group` label from `policy.ini`.
9. `category` comes from the reading's tariff code in `tariff_catalogue.csv`.
10. `posted_usd_cents` is the gross amount multiplied by the USD rate and by
    100, built as one exact decimal expression and quantized exactly once, at
    that point and nowhere earlier, to a whole cent under the `[rounding]` mode
    in `policy.ini`.

## Malformed readings

A reading is malformed when any field it needs fails to parse under the rules
above, or when any lookup in the chain misses: an unknown account, tariff code,
meter site, collector or postcode prefix, a day that does not exist, a currency
with no usable rate, a legacy line without exactly eleven fields, an
`amount_minor` that is not a JSON integer, or a levy kind that is neither
`surcharge` nor `rebate`. A malformed reading is skipped, is counted against its
own reading file, and appears in nothing else. An empty `note`, `memo`,
`firmware` or `inspector` is normal and never a reason to skip.

## Orphan charge links

A remittance whose `charge_reading_id` is non-empty after trimming, and which
does not equal the `reading_id` of any row present in `consumption.csv`, is an
orphan. Presence in `consumption.csv` is judged on the rows of that file as they
stand, with no regard for whether the charge itself posted. An orphan is
reported by id, is excluded from every total and never reaches the wallet. A
`charge_reading_id` that is empty after trimming is not a link at all and the
remittance is ordinary.

This test reads the amended `charge_reading_id` and nothing else, and it runs
before any other field of the remittance is parsed. A remittance the test names
is therefore an orphan and not a malformed reading, even where another of its
fields would have failed to parse: it is reported among the orphan ids and is
counted in no file's skipped tally. Orphan wins over malformed every time the
two would both apply.

An orphan therefore reaches `orphan_remittance_ids` and
`orphan_remittance_count` and nothing else. It raises neither `skipped_count`
nor any entry of `skipped_by_source`, and neither `held_count` nor any entry of
`held_by_source`.

A link that does name a row present in `consumption.csv` is not an orphan, and
nothing about the state of that row changes the remittance: a remittance whose
link names a charge that was itself skipped as malformed, or that was credit
held, is an ordinary remittance and goes on to the wallet like any other.

## The prepay wallet gate

Each account keeps one running wallet balance in USD cents. It opens at
`opening_credit_minor` divided by 100, converted to USD cents by the rule in
step 10 using the rate for `opening_currency` on the `opening_rate_date` from
`policy.ini`.

The account's readings are then taken one at a time in order of UTC instant,
with `reading_id` compared as text breaking a shared instant. Malformed readings
and orphans are gone before this point and take no part.

A reading whose `posted_usd_cents` is zero or positive posts and raises the
wallet by that amount. A reading whose `posted_usd_cents` is negative posts only
when the balance it would leave behind is at or above the `[disconnection]`
floor for that account's tariff class; when it would leave the balance below
that floor the reading is credit held, the wallet does not move, and the reading
is reported by id, kept out of `normalized.jsonl` and out of every money total,
and counted against its own reading file and its own zone and tariff class. A
held reading does not end the wallet: later readings on the same account are
judged against the balance that the hold left standing.

An account whose opening wallet is already below its class floor is not an error
and holds nothing by itself.

## The canonical posting record

One JSON object per posted reading with exactly these sixteen keys:
`reading_id`, `posting_date`, `utc_instant`, `billing_cycle`, `account_id`,
`tariff_class`, `zone`, `tariff_code`, `category`, `kind`, `units`,
`posted_usd_cents`, `currency`, `source`, `route_group`, `meter_site`.

- `utc_instant` is written `YYYY-MM-DDTHH:MM:SSZ` and `posting_date`
  `YYYY-MM-DD`.
- `units` is the integer units consumed, `0` for levies.
- `source` is the reading file the row came from, extension included:
  `consumption.csv`, `remittances.tsv`, `levies.jsonl` or `legacy_reads.txt`.
- `meter_site` is the reading's meter site id, and `null` for a levy.
- Net units count a `consumption` as `+units`, a `remittance` as `-units`, and
  every other kind as zero, whatever money the reading carries.

## Serialization

`normalized.jsonl` holds one posted record per line, ordered by `reading_id`
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

Money figures are sums of `posted_usd_cents` over posted records. Every map is
emitted with sorted keys. An artifact is right only when every value in it is
right.

`summary.json`:
`event_count`, `skipped_count`, `held_count`, `orphan_remittance_count`,
`total_usd_cents`, `net_units`, `wallet_closing_usd_cents`, and the breakdown
maps `by_zone`, `by_tariff_class`, `by_kind`, `by_category`, `by_route_group`,
`by_billing_cycle` and `by_source`, each mapping a value that occurs among the
posted records to its summed USD cents. `wallet_closing_usd_cents` is the sum of
every account's closing wallet over every account `accounts.csv` names,
including those with no readings at all.

`data_quality.json`:
`input_files` (the name of every regular file in the input directory, sorted),
`records_by_source` (each `source` that produced at least one posted record
mapped to that count), `skipped_by_source` and `held_by_source` (one entry per
reading file the input directory actually holds, mapped to its count, zeros
included; a reading file the directory does not hold takes no entry at all),
`skipped_count`, `held_count`, `orphan_remittance_count`,
`held_reading_ids`, `orphan_remittance_ids` and `unmatched_amendment_targets`,
the last three sorted and free of duplicates.

`product_summary.json`: a `tariffs` array with one entry per tariff code in
`tariff_catalogue.csv`, ordered by tariff code, including codes no reading
touched. Each entry carries `tariff_code`, `category`, `event_count`,
`total_usd_cents`, `net_units`, `installed_litres`, `service_floor_litres` and
`net_volume_litres`, where the two capacity figures are the sums over that
code's `meter_sites.csv` rows and `net_volume_litres` is net units multiplied by
`unit_volume_litres` and by `litres_per_kilolitre`, built as one exact decimal
expression and quantized exactly once to a whole litre under the `[rounding]`
mode.

`region_central.json`, `region_east.json`, `region_north.json`,
`region_south.json` and `region_west.json`: one file per top level zone, all
five written every run even when a zone drew nothing. Keys: `zone`,
`event_count`, `total_usd_cents`, `net_units`, `held_count`, `accounts` (the
sorted distinct ids that contributed a posted record), `by_kind` and
`by_category`.

`segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json`
and `segment_smb.json`: one file per tariff class, all four written every run.
The same keys with `tariff_class` in place of `zone`, plus
`disconnection_floor_usd_cents`, that class's floor from `policy.ini`.

## The closing report

The transform writes files; the closing message carries nine figures that no
artifact holds. Each is counted over the whole corpus the run was pointed at:

1. `held_value_usd_cents`: the sum of `posted_usd_cents` over every credit held
   reading.
2. `held_accounts`: how many distinct accounts had at least one credit held
   reading.
3. `carry_back_rate_events`: how many posted readings took their rate from an
   earlier date because their posting date had no row for their currency.
4. `day_shift_events`: how many posted readings have a `posting_date` that
   differs from the calendar date written in their own `read_ts`.
5. `amended_readings`: how many distinct reading ids had at least one amendment
   applied to them. The replacement counts as applied whenever the amendment
   named a column of that reading's own file, including where the text it wrote
   is the text that was already there.
6. `half_cent_events`: how many posted readings had a money product whose
   fractional part was exactly half a cent before quantizing.
7. `underfunded_accounts`: how many accounts open below their own class floor.
8. `uncatalogued_capacity_litres`: the sum of `installed_litres` over every
   `meter_sites.csv` row whose tariff code is absent from
   `tariff_catalogue.csv`.
9. `stale_link_remittances`: how many posted remittances carry a
   `charge_reading_id` that names a `consumption.csv` row that was itself
   skipped as malformed. Posted here means the remittance reached
   `normalized.jsonl`; a stale link is a reporting observation and never a
   reason to skip or hold the remittance that carries it.
