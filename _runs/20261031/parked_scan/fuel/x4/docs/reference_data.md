# Reference data

The files under `ref/` are UTF-8. CSV and TSV files have a header row. Dates
are written `YYYY-MM-DD`; a date range given by two dates includes both.

## processors.json

One JSON object.

- `settlement_month`: the settlement month, `YYYY-MM`.
- `processors`: a list with one object per processor:
  - `name`: the processor name used in ledger ids and output keys;
  - `export`: the path of its export, relative to the data directory;
  - `format`: the export format (`csv`, `fixed-width`, `jsonl`, `xml`, `tsv`);
  - `home_region`: the region of the processor's head office;
  - `head_office_offset`: the UTC offset of the processor's head office,
    written `+HH:MM` or `-HH:MM` (present for marlow);
  - `pump_test_type`: the record type the processor uses for pump tests
    (present for kestrel);
  - `layout`: the field layout of a fixed-width export (present for lumen):
    a list of objects with `field`, `start` (1-based column of the first
    character) and `width`.

## sites.csv

Columns `site_id,region,utc_offset,jurisdiction`. One row per site.
`utc_offset` is the site's fixed offset from UTC all year, written `+HH:MM`
or `-HH:MM`. `jurisdiction` is the tax jurisdiction used in tax_rates.tsv.

## cards.csv

Columns `card_number,account_id,valid_from,valid_to`. A card is held by the
account of the row whose range contains the date; an empty `valid_to` means
the row has no end. A card can pass from one account to another, giving one
row per holder. A sale line whose card has no holder on its business date is
rejected `unknown_card`.

Example, on made-up values: card 1111000000000001 has the rows
`1111000000000001,A1,2041-01-01,2041-05-14` and
`1111000000000001,A2,2041-05-15,`. A sale on 2041-05-14 belongs to A1 and a
sale on 2041-05-15 belongs to A2.

## accounts.csv

Columns `account_id,segment,effective_from,closed_on`. An account has one row
per segment it has held. The segment in force on a date is the one on the row
with the latest `effective_from` on or before that date.

Example, on made-up values: account A7 has rows with segment `smb` from
2041-01-01 and `corporate` from 2041-04-10. A row dated 2041-04-09 has
segment `smb`; a row dated 2041-04-10 has segment `corporate`.

`closed_on` is the last date on which the account may settle. It is repeated
on every row of the account and is empty while the account is open. A sale
line whose business date is after `closed_on` is rejected `account_closed`.

Example, on made-up values: account A9 has `closed_on` 2041-07-20. A sale
dated 2041-07-20 can settle; a sale dated 2041-07-21 is rejected
`account_closed`.

## products.xml

One `<product>` element per catalogue product, with attributes `code`,
`kind` (`fuel` or `nonfuel`), `tax_class` and `unit` (`litre`, `kg` or
`each`). Each product has one `<alias processor="..." code="..."/>` child per
processor that sells it.

## discount_tiers.ini

- `[eligible]`: `segments`, a comma-separated list of the segments that earn
  discounts.
- `[tier.<name>]`: one section per tier, with `floor_litres` and
  `rate_per_litre` (dollars per litre). The tier name is the part of the
  section name after `tier.`.
- `[cap]`: one key per segment, the most discount, in dollars, that one
  account may receive in one month while in that segment.

## tax_rates.tsv

Columns `jurisdiction`, `tax_class`, `rate` and `effective_from`. A rate
applies from its `effective_from` until the next row of the same
jurisdiction and tax class.

Example, on made-up values: jurisdiction JX9, class road_fuel, has rate
0.1000 from 2041-01-01 and rate 0.1200 from 2041-06-16. A line dated
2041-06-15 uses 0.1000 and a line dated 2041-06-16 uses 0.1200.

## batches.log

One event per line: `<ISO 8601 UTC timestamp> <processor> <batch> <event>`,
in the order the events happened. Events are `OPENED`, `CLOSED`,
`SUPERSEDED`, `WITHDRAWN` and `REINSTATED`. A batch is identified by its
processor and batch name together.

The standing of a batch is set by its last `SUPERSEDED`, `WITHDRAWN` or
`REINSTATED` event. A batch whose last such event is `SUPERSEDED` has every
line rejected `superseded_batch`; one whose last such event is `WITHDRAWN`
has every line rejected `withdrawn_batch`. A batch with none of these events,
or whose last one is `REINSTATED`, is live.

Example, on made-up values: batch B5 has the events `OPENED`, `CLOSED`,
`WITHDRAWN` and `REINSTATED`, in that order. Its lines are judged like the
lines of any live batch.
