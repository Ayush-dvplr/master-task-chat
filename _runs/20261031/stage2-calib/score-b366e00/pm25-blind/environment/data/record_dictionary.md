# Record dictionary

This dictionary describes every file of an extract of the Harbourline PM2.5 network, field by field.
The monitoring standard (`monitoring_standard.md`) says how the records become daily values and
compliance findings, and the report layout (`report_layout.md`) says what the reports hold.

## Conventions shared by every file

- Text files are UTF-8 with LF line endings. A file may begin with a byte-order mark, which belongs
  to no field.
- CSV files are comma separated, quote fields in the usual CSV way, and carry one header row.
- An empty CSV field means the value is absent.
- Times are written `YYYY-MM-DDTHH:MM` and name whole minutes. A time is a true UTC time unless its
  column or file says otherwise.
- Where a row covers a period between two times, the period includes its first time and excludes
  its last time, unless this dictionary says otherwise for that file.
- Field values are compared exactly as written, except channel labels (see Unit deployments).
- Rows of a CSV file are in no particular order.
- Site ids are the letter `S` followed by a whole number written without leading zeros. Unit ids are
  `AQ` followed by digits. Asset tags are `T-` followed by digits. Entry ids are `E` followed by a
  whole number. No unit id is also an asset tag.

## Asset tags (`asset_tags.csv`)

Columns: `asset_tag`, `unit_id`, `valid_from_utc`, `valid_to_utc`.

Each row says that the asset tag names the unit from `valid_from_utc` up to `valid_to_utc`; an empty
`valid_to_utc` means the row has no end. A tag names at most one unit at any instant, and a tag may
name different units at different times.

## Card readings (`card_readings.csv`)

Columns: `unit_id`, `card_stamp`, `frame`, `pm25_raw`, `status`.

One row is one reading taken from the memory card of a sensor unit. A unit averages the
concentration over consecutive 15-minute intervals and writes one row at the end of each interval.
A card holds no two rows with the same stamp. A unit that is powered off writes nothing, so a card
can have gaps.

- `card_stamp` is the reading of the unit's own clock at the end of the reading's averaging
  interval. A unit's clock is set to UTC but runs a whole number of minutes ahead of or behind true
  UTC, never by more than 19 minutes either way. The clock reading minus the true UTC time is the
  unit's clock offset, and the offset holds for every row on the unit's card. The true end of a
  reading's averaging interval is its card stamp minus the clock offset.
- The instant a reading represents is the true end of its averaging interval. When that instant
  falls exactly on the hour, the reading represents the hour that the interval closes, not the hour
  that begins at that instant.
- `frame` is the unit's packet counter for the reading, a whole number from 0 to 255. It goes up by
  one for each row the unit writes and returns to 0 after 255.
- `pm25_raw` is the uncorrected concentration in tenths of a microgram per cubic metre, a
  non-negative whole number. It is empty when the sensor produced no value for the interval.
- `status` is empty for an ordinary reading. Any other value is a letter code that marks the
  interval as a zero check, a span check or a sensor fault.

## Extract manifest (`extract_manifest.json`)

A JSON object with the keys `network` (text), `report_id` (text), `first_day` (a date written
`YYYY-MM-DD`), `days` (a whole number), `span_register_revision` (text) and `policy_revision`
(text). The report window is the run of `days` consecutive days of local standard time that starts
with `first_day`. The two revisions name the span register and the network policy this extract was
cut against.

## Maintenance log (`maintenance_log.json`)

A JSON object with the keys `time_basis` and `entries`.

- `time_basis` is `civil` or `utc` and gives the clock every time in the file is written in: civil
  time of the network zone, or true UTC.
- `entries` is a list of objects with the keys `site_id`, `begins`, `ends` and `work`. Each entry is a
  maintenance window at the site, from `begins` up to `ends`. `work` is free text.
- No `begins` or `ends` time falls in an hour that civil time skips or repeats.

## Network policy (`network_policy*.json`)

One or more JSON files whose names begin with `network_policy`. Each holds one object with the keys
`revision` (text), `daily_standard` (a concentration in micrograms per cubic metre, written as decimal
text with one digit after the point), `hour_min_readings`, `day_min_hours` and
`site_min_valid_day_percent` (whole numbers). The policy in force is the file whose `revision` is
the revision the manifest names.

## Receipt journal (`receipt_journal.csv`)

Columns: `channel`, `received_utc`, `frame`.

The network base station writes one row for each radio packet it receives. A unit sends one packet
for each row it writes on its card, on the unit's channel, in the true minute at which that row's
averaging interval ends, and the packet carries the row's frame. The station records a received
packet once, on the channel it arrived on, at the true minute it was sent, with the packet's frame.
Packets can be lost, and the station never records a packet that no unit sent. No channel ever
carries two packets in the same minute.

## Site register (`site_register.csv`)

Columns: `site_id`, `site_name`, `district`, `operator_class`.

Every monitoring site of the network. `district` is the district the site lies in; the reporting
districts are `North`, `South`, `West` and `East`, and a site in any other district belongs to no
district rollup. `operator_class` is `commercial` for a fence-line monitor run under a facility permit
and `public` for an agency monitor.

## Span registers (`span_register*.csv`)

One or more CSV files whose names begin with `span_register`, with the columns `revision`,
`entry_id`, `unit_ref`, `effective_utc`, `span_factor`, `action` and `target_entry`. Every row of one
file carries that file's revision, and the span register in force is the file whose revision is the
revision the manifest names. The register's entries, read as a whole, give each unit's span factor
over time.

- `action` is `set`, `amend` or `withdraw`. Columns an action does not use are empty.
- A `set` entry gives the span factor `span_factor` (decimal text) to the unit `unit_ref` from the
  instant `effective_utc` on. `unit_ref` is a unit id or an asset tag. An asset tag stands for the unit
  the tag names at `effective_utc`; an entry whose tag names no unit at that instant does nothing.
- An `amend` entry replaces the span factor of the `set` entry that `target_entry` names with its own
  `span_factor`; the unit and the effective instant stay those of the set entry. When several live
  amend entries name one set entry, the one with the highest entry number governs. An amend entry
  that names anything other than a set entry does nothing.
- A `withdraw` entry makes the `set` or `amend` entry that `target_entry` names void: a void entry
  counts as if it were absent. A withdraw entry that names a withdraw entry, or names no entry of the
  register, does nothing.
- A unit's span factor in force at an instant comes from the live set entry for that unit with the
  latest effective instant at or before that instant; an entry takes effect at its effective instant.
  Of two live set entries for one unit with the same effective instant, the higher entry number
  governs. A unit with no live set entry at or before an instant has no span factor in force then.

## Unit deployments (`unit_deployments.csv`)

Columns: `unit_id`, `site_id`, `channel`, `installed_utc`, `removed_utc`.

Each row says that the unit stood at the site from `installed_utc` up to `removed_utc`; an empty
`removed_utc` means the unit is still in place. A unit's deployments never overlap, and every unit
with a card appears here. A unit keeps one radio channel throughout. Channel labels are compared
without regard to letter case and to spaces before or after the label; a label's written form is the
label in capital letters with those spaces removed.

## Zone rules (`zone_rules.json`)

A JSON object with the keys `standard_offset_minutes` and `daylight_saving`.

- Local standard time is true UTC plus `standard_offset_minutes`.
- `daylight_saving` is a list of objects with the keys `begins`, `ends` and `shift_minutes`.
  Daylight saving is in force from `begins` up to `ends`, both written in civil time. Civil time is local standard time plus `shift_minutes` while
  daylight saving is in force, and local standard time at all other times.
