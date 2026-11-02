# TY31 reserve-gated dispensing clearing run: the written contract

This directory is a flat export of one tariff year of dispensing activity from
a medical supply claims exchange. It holds four claim files, eight reference
files, one policy file, and this contract. There is no code.

No single file clears a claim. Every claim reaches its region, its currency,
its rate, its tariff period and its lane only through a chain that crosses
several reference files, and whether a claim is cleared at all depends on the
state of its member's reserve ladder at the moment the claim lands. Row order
in an input file is never significant except in the two places this contract
names file order as the tie-break.

Every field value is trimmed of leading and trailing whitespace before it is
used. Identifiers (`claim_id`, `member_id`, `item_code`, `depot`,
`postal_prefix`, `rate_date`, `dispense_claim_id`) are then compared exactly.
Gateway ids and all enumerated labels (`segment`, `zone`, `category`, `lane`,
`kind`, `currency`) are compared after trimming and case folding, and are
emitted case folded: lower case for every label, upper case for `currency`.

## Claim files

- `dispenses.csv`, comma delimited:
  `claim_id,booked_ts,member_id,item_code,depot,quantity,unit_price,currency,gateway`.
  Kind `dispense`. The gross amount is `quantity * unit_price`, always
  positive.
- `recoveries.tsv`, tab delimited:
  `claim_id,booked_ts,member_id,item_code,depot,quantity,recovered_amount,currency,gateway,dispense_claim_id`.
  Kind `recovery`. The gross amount is minus the absolute value of
  `recovered_amount`, whatever sign the column carries.
- `assessments.jsonl`, one JSON object per line with the keys `claim_id`,
  `booked_ts`, `member_id`, `item_code`, `kind`, `amount_minor`, `currency`
  and an optional `note`. `kind` is `levy` or `rebate` in any letter case.
  `amount_minor` must be a JSON integer and carries its own sign; the gross
  amount is `amount_minor` divided by 100. An assessment has no depot and no
  gateway, and its quantity is `0`.
- `archive.txt`, pipe delimited, encoded latin-1. Blank lines and lines whose
  first non-blank character is `#` carry no claim. Every other line has
  exactly eleven fields:
  `claim_id|booked_ts|member_id|item_code|depot|kind|quantity|amount|currency|gateway|memo`.
  `amount` is the line total and is unsigned in practice. The `kind` token is
  read case folded like every other label, so `dispense` and `levy` take
  `+abs(amount)`, `recovery` and `rebate` take `-abs(amount)`, and only a token
  outside those four is malformed. `memo` is informational and may be empty.

`quantity` is an integer written with ASCII digits and nothing else. A value
carrying a sign, a decimal point, a word, a digit from another script, or
nothing at all is malformed. `quantity` may be `0`: such a claim contributes
its full money and no units.

`booked_ts` is written `YYYY-MM-DDTHH:MM:SS`. In `dispenses.csv`,
`recoveries.tsv` and `archive.txt` it is local wall-clock time at the
dispensing depot. In `assessments.jsonl` it carries a trailing `Z` and is
already UTC.

## Reference files

- `members.csv`:
  `member_id,name,segment,postal_code,opening_reserve_minor,opening_currency,updated_at`.
  `segment` is one of `consumer`, `smb`, `corporate`, `enterprise`.
  `opening_reserve_minor` is a signed integer in the minor units of
  `opening_currency`. A `member_id` may appear on several rows; the row with
  the greatest `updated_at` is the one that counts, and when two rows share
  the greatest `updated_at` the later of them in file order counts.
- `zones.csv`: `postal_prefix,zone,parent_zone,steward,default_currency`. A
  postal code is written `<prefix>-<suffix>`; the text before the first `-` is
  the `postal_prefix`. `parent_zone` is empty on a top level zone and
  otherwise names the zone one level up. The five top level zones are
  `central`, `east`, `north`, `south` and `west`. A record's reporting region
  is the top level ancestor of the zone its postal prefix names.
  `default_currency` belongs to the matched prefix row. `steward` is
  informational.
- `stock_ledger.csv`:
  `item_code,depot,postal_code,tz_offset_minutes,on_hand_grams,reorder_point_grams`,
  one row per stocking pair, so an item stocked in four depots appears four
  times. Every row for a depot repeats that depot's `postal_code` and
  `tz_offset_minutes`. A depot is known when it appears on any row. Stock
  figures are summed over every row for an item code.
- `gateways.csv`: `gateway,lane,device`. Maps the gateway that booked the
  claim to its `lane`. `device` is informational.
- `item_catalog.csv`: `item_code,name,category,pack_mass_kg,active`. Gives the
  item's `category` and its pack mass in kilograms. An item counts whether or
  not it is `active`.
- `fx_rates.csv`: `rate_date,currency,usd_rate`, at most one row per currency
  per day, USD listed at 1. The rate that applies to a clearing date is the
  row for that currency on that exact date; when that date has no row for the
  currency, the row for that currency on the most recent earlier date applies.
- `tariff_calendar.json`: a `periods` array of `period`, `start`, `end` and
  `weeks`. A clearing date belongs to the period whose closed `start` to `end`
  span contains it. Periods do not follow calendar months and do not cover the
  whole year; a date no period covers takes the `unassigned_period` label from
  `policy.ini`, which is not an error.
- `amendments.log`: one line per log entry, written
  `<utc_ts> <level> <message...>`. A line whose message begins with the word
  `amendment` carries the tokens `target=<claim_id>`, `field=<name>` and
  `value=<text>`, and replaces the named field of the named claim with that
  text before any parsing of that claim happens. `value` may be empty, which
  sets the field to the empty string. Any other line is informational. When
  several amendments name the same claim and the same field, the one with the
  greatest `<utc_ts>` wins, and when two of them share the greatest `<utc_ts>`
  the later of them in file order wins. An amendment whose `field` is not a
  column of its target's own claim file is ignored, and so is one naming
  `claim_id`, which identifies the claim and is never replaced. An amendment
  whose `target` matches no claim id in any claim file is unmatched and is
  reported.

## policy.ini

`policy.ini` carries the contract constants: the per segment reserve floors in
USD cents under `[reserve]`, the `opening_rate_date` under `[ladder]`, the
money and mass rounding mode under `[rounding]`, `grams_per_kilogram` under
`[mass]`, and the `unassigned_period` and `assessment_lane` labels under
`[labels]`. Read them from the file; they are not repeated here.

## Clearing one claim

1. Apply every amendment that names this claim and a column of its own claim
   file.
2. The member comes from `members.csv` and gives the `segment` and, for
   assessments only, the postal code.
3. The postal code of a dispense, recovery or archive claim is its dispensing
   depot's postal code from `stock_ledger.csv`. The postal code of an
   assessment is its member's own.
4. The reporting `region` is the top level ancestor of the zone that
   `zones.csv` gives for that postal code's prefix.
5. `currency` is the claim's own currency when it has one, and otherwise the
   `default_currency` of the prefix row matched in step 4.
6. The UTC instant of a dispense, recovery or archive claim is its local
   `booked_ts` shifted by its depot's `tz_offset_minutes`, which may be
   negative. An assessment's `booked_ts` is already UTC. The `clearing_date`
   is the calendar date of the UTC instant, and the tariff period follows from
   that date. `booked_ts` must name a real calendar day; a day that does not
   exist is malformed.
7. The USD rate follows from `clearing_date` and `currency` under the rule in
   `fx_rates.csv` above. A claim whose currency has no row on or before its
   clearing date is malformed.
8. `lane` comes from the claim's gateway in `gateways.csv`. An assessment
   takes the `assessment_lane` label from `policy.ini`.
9. `category` comes from the claim's item code in `item_catalog.csv`.
10. `cleared_usd_cents` is the gross amount multiplied by the USD rate and by
    100, built as one exact decimal expression and quantized exactly once, at
    that point and nowhere earlier, to a whole cent under the `[rounding]`
    mode in `policy.ini`.

## Malformed claims

A claim is malformed when any field it needs fails to parse under the rules
above, or when any lookup in the chain misses: an unknown member, item code,
depot, gateway or postal prefix, a day that does not exist, a currency with no
usable rate, an archive line without exactly eleven fields, an `amount_minor`
that is not a JSON integer, or an assessment kind that is neither `levy` nor
`rebate`. A malformed claim is skipped, is counted against its own claim file,
and appears in nothing else. An empty `note`, `memo`, `device` or `steward` is
normal and never a reason to skip.

## Orphan recovery links

A recovery whose `dispense_claim_id` is non-empty after trimming, and which
does not equal the `claim_id` of any row present in `dispenses.csv`, is an
orphan. Presence in `dispenses.csv` is judged on the rows of that file as they
stand, with no regard for whether the dispense itself cleared. An orphan is
reported by id, is excluded from every total and never reaches the ladder. A
`dispense_claim_id` that is empty after trimming is not a link at all and the
recovery is ordinary.

This test reads the amended `dispense_claim_id` and nothing else, and it runs
before any other field of the recovery is parsed. A recovery the test names is
therefore an orphan and not a malformed claim, even where another of its
fields would have failed to parse: it is reported among the orphan ids and is
counted in no file's skipped tally. Orphan wins over malformed every time the
two would both apply.

## The reserve ladder

Each member keeps one running reserve in USD cents. It opens at
`opening_reserve_minor` divided by 100, converted to USD cents by the rule in
step 10 using the rate for `opening_currency` on the `opening_rate_date` from
`policy.ini`.

The member's claims are then taken one at a time in order of UTC instant, with
`claim_id` compared as text breaking a shared instant. Malformed claims and
orphans are gone before this point and take no part.

A claim whose `cleared_usd_cents` is zero or positive is cleared and raises
the reserve by that amount. A claim whose `cleared_usd_cents` is negative is
cleared only when the reserve it would leave behind is at or above the
`[reserve]` floor for that member's segment; when it would leave the reserve
below that floor the claim is reserve blocked, the reserve does not move, and
the claim is reported by id, kept out of `normalized.jsonl` and out of every
money total, and counted against its own claim file and its own region and
segment. A blocked claim does not end the ladder: later claims on the same
member are judged against the reserve that the block left standing.

A member whose opening reserve is already below its segment floor is not an
error and blocks nothing by itself.

## The canonical clearing record

One JSON object per cleared claim with exactly these sixteen keys: `claim_id`,
`clearing_date`, `utc_instant`, `tariff_period`, `member_id`, `segment`,
`region`, `item_code`, `category`, `kind`, `quantity`, `cleared_usd_cents`,
`currency`, `source`, `lane`, `depot`.

- `utc_instant` is written `YYYY-MM-DDTHH:MM:SSZ` and `clearing_date`
  `YYYY-MM-DD`.
- `quantity` is the integer quantity, `0` for assessments.
- `source` is the claim file the row came from, extension included:
  `dispenses.csv`, `recoveries.tsv`, `assessments.jsonl` or `archive.txt`.
- `depot` is the claim's depot id, and `null` for an assessment.
- Net units count a `dispense` as `+quantity`, a `recovery` as `-quantity`,
  and every other kind as zero, whatever money the claim carries.

## Serialization

`normalized.jsonl` holds one cleared record per line, ordered by `claim_id`
compared as text, each line a compact JSON object with sorted keys, no spaces
after the separators, and a trailing newline on every line. Every `.json`
artifact is a JSON document with sorted keys, a two space indent, and a
closing newline.

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

Money figures are sums of `cleared_usd_cents` over cleared records. Every map
is emitted with sorted keys. An artifact is right only when every value in it
is right.

`summary.json`:
`event_count`, `skipped_count`, `blocked_count`, `orphan_recovery_count`,
`total_usd_cents`, `net_units`, `reserve_closing_usd_cents`, and the breakdown
maps `by_region`, `by_segment`, `by_kind`, `by_category`, `by_lane`,
`by_tariff_period` and `by_source`, each mapping a value that occurs among the
cleared records to its summed USD cents. `reserve_closing_usd_cents` is the
sum of every member's closing reserve over every member `members.csv` names,
including those with no claims at all.

`data_quality.json`:
`input_files` (the name of every regular file in the input directory, sorted),
`records_by_source` (each `source` that produced at least one cleared record
mapped to that count), `skipped_by_source` and `blocked_by_source` (each of
the four claim files present in the input directory mapped to its count, zeros
included), `skipped_count`, `blocked_count`, `orphan_recovery_count`,
`blocked_claim_ids`, `orphan_recovery_claim_ids` and
`unmatched_amendment_targets`, the last three sorted and free of duplicates.

`product_summary.json`: a `products` array with one entry per item code in
`item_catalog.csv`, ordered by item code, including items no claim touched.
Each entry carries `item_code`, `category`, `event_count`, `total_usd_cents`,
`net_units`, `on_hand_grams`, `reorder_point_grams` and `net_mass_grams`,
where the two stock figures are the sums over that item's `stock_ledger.csv`
rows and `net_mass_grams` is net units multiplied by `pack_mass_kg` and by
`grams_per_kilogram`, built as one exact decimal expression and quantized
exactly once to a whole gram under the `[rounding]` mode.

`region_central.json`, `region_east.json`, `region_north.json`,
`region_south.json` and `region_west.json`: one file per top level region, all
five written every run even when a region drew nothing. Keys: `region`,
`event_count`, `total_usd_cents`, `net_units`, `blocked_count`, `members` (the
sorted distinct ids that contributed a cleared record), `by_kind` and
`by_category`.

`segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json`
and `segment_smb.json`: one file per segment, all four written every run. The
same keys with `segment` in place of `region`, plus
`reserve_floor_usd_cents`, that segment's floor from `policy.ini`.

## The closing report

The transform writes files; the closing message carries nine figures that no
artifact holds. Each is counted over the whole corpus the run was pointed at:

1. `blocked_value_usd_cents`: the sum of `cleared_usd_cents` over every
   reserve blocked claim.
2. `blocked_members`: how many distinct members had at least one reserve
   blocked claim.
3. `carry_forward_rate_events`: how many cleared claims took their rate from
   an earlier date because their clearing date had no row for their currency.
4. `day_shift_events`: how many cleared claims have a `clearing_date` that
   differs from the calendar date written in their own `booked_ts`.
5. `amended_events`: how many distinct claim ids had at least one amendment
   applied to them.
6. `half_cent_events`: how many cleared claims had a money product whose
   fractional part was exactly half a cent before quantizing.
7. `underwater_members`: how many members open below their own segment floor.
8. `uncatalogued_stock_grams`: the sum of `on_hand_grams` over every
   `stock_ledger.csv` row whose item code is absent from `item_catalog.csv`.
9. `stale_link_recoveries`: how many cleared recoveries carry a
   `dispense_claim_id` that names a `dispenses.csv` row that was itself
   skipped as malformed.
