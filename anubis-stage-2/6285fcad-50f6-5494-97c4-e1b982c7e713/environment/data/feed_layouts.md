# Shard layouts

The ingest catalog gives the layout id of every listed shard. Every shard is UTF-8. Station tokens resolve under
handbook H5 at the record instant. A record is one reading value; the fields below say where its station, sensor,
instant, value, unit, quality, revision and void mark come from. Where a layout has no sensor field the sensor is P;
where it has no quality field the quality is G; where it has no revision field the revision is 1. Values are decimals
as written. JSON numbers are exact decimals as written.

## Summary

| layout | format | time | unit | sensor | quality | void |
|---|---|---|---|---|---|---|
| L01 | csv | UTC ISO | register | P/B | G S E X | void column |
| L02 | csv wide | LST date + hour | row | P | none | none |
| L03 | tsv | UTC epoch s | column | P/B | OK SUS EST FLT | status |
| L04 | tsv | wall clock | register | P/B | A S E F | none |
| L05 | psv | UTC epoch ms | cm | P/B | 0 1 2 9 | vd |
| L06 | psv | ISO offset | suffix | P | g s e x | none |
| L07 | jsonl | LST compact | field | P/B | G S E X | x |
| L08 | jsonl | UTC ISO | field | P/B | words | meta.void |
| L09 | ndjson wide | UTC hour | row | P | none | none |
| L10 | ndjson | UTC epoch s | m | B | G S E X | deleted |
| L11 | xml | UTC ISO | register | P/B | words | void attribute |
| L12 | xml | zoned | attribute | P | 10 30 40 90 | none |
| L13 | txt fixed | LST date + HHMM | column | P | G S E X | none |
| L14 | txt log | UTC | suffix | P/B | G S E X | VOID lines |
| L15 | yaml | UTC epoch s | block | P/B | g s e x | none |
| L16 | yml | UTC minute key | field | P | none | none |
| L17 | json series | UTC epoch start + step | meta or run | P/B | none | none |
| L18 | sqlite | LST serial | column | P/B | G S E X | void column |
| L19 | db | UTC epoch s | mm | P/B | flag | voids table |
| L20 | csv | LST text | ft | P | none | none |

## L01

- csv with header `station,sensor,obs_utc,stage,qual,rev,void`; lines starting with # and blank lines are not records
- obs_utc: UTC ISO with Z
- stage: decimal in the equipment register unit of the station and sensor
- sensor: P or B
- qual: G, S, E, X
- rev: integer revision
- void: 1 marks a void copy (stage empty), 0 otherwise

## L02

- csv with header `site_id,date_lst,hour,m00,m15,m30,m45,unit,rev`; one row per station, unit, revision and LST hour
- m00..m45: values at minute 00, 15, 30 and 45 of the hour; an empty cell is no record
- date_lst and hour: LST date and hour 0 to 23
- a row whose hour is MEAN is a summary row and not a record
- unit: ft or m for the whole row
- sensor: always P; quality: none (G)
- rev: integer revision; no voids

## L03

- tsv with header `gauge chan t_epoch h unit flag revision status`; lines starting with # are not records
- t_epoch: UTC epoch seconds
- h: decimal with a decimal comma
- unit: FT or M
- chan: 1 is P, 2 is B
- flag: OK=G, SUS=S, EST=E, FLT=X
- status: VOID marks a void copy, ACTIVE otherwise

## L04

- tsv with header `STN SENSOR WALLCLOCK GH Q REV`; the header line repeats every 500 records and is not a record
- WALLCLOCK: local wall-clock time YYYY-MM-DD HH:MM (daylight time applies, H3)
- GH: decimal in the equipment register unit
- SENSOR: PRI is P, BAK is B
- Q: A=G, S=S, E=E, F=X
- REV: integer revision; no voids

## L05

- psv with header `site|sens|ts_ms|value_cm|q|rv|vd`
- ts_ms: UTC epoch milliseconds
- value_cm: centimetres
- sens: 1 is P, 2 is B
- q: 0=G, 1=S, 2=E, 9=X
- rv: revision
- vd: Y marks a void copy

## L06

- psv with header `alias|when|stage|code|ver`
- when: ISO time with a numeric offset (any offset)
- stage: decimal followed by its unit, ft or m, in any case and with or without a space
- code: g, s, e, x
- sensor: always P
- ver: revision; no voids

## L07

- JSON Lines; objects with `type` hb are heartbeats and not records
- keys: s station, k sensor P or B, t LST compact YYYYMMDDTHHMM,
- v value as a string, u unit ft or m, q G/S/E/X, r revision, x true for a void copy

## L08

- JSON Lines with nested objects
- station.id: token
- reading.time_utc: ISO with +00:00
- reading.gh.value: JSON number (null for a void copy); reading.gh.unit: FT or M
- meta.channel: primary is P, backup is B
- meta.quality: good=G, suspect=S, estimated=E, fault=X
- meta.rev, meta.void

## L09

- newline-delimited JSON, one object per station, unit, revision and UTC hour
- hour_utc: YYYY-MM-DDTHH (UTC)
- vals: four values at minutes 00, 15, 30, 45 of that UTC hour; null is no record
- unit: ft or m
- sensor: always P; quality: none (G)
- rev: revision; no voids

## L10

- newline-delimited JSON of backup sensors only (sensor B)
- keys: id token, epoch UTC seconds, stage_m metres (null for a void copy),
- qa G/S/E/X, rev revision, deleted 1 for a void copy

## L11

- XML: `<batch>` holds `<site code=token>` elements with `<r>` readings; comments are not records
- r@s: P or B
- r@t: UTC ISO with Z
- r@v: decimal in the equipment register unit
- r@q: GOOD=G, SUSP=S, EST=E, FAULT=X
- r@rev: revision; r@void=1 marks a void copy

## L12

- XML: `<export>` holds `<reading>` elements
- station: token
- time@zone: UTC, LST or LOCAL (wall clock, H3); text DD/MM/YYYY HH:MM
- value@unit: ft or m
- qual: 10=G, 30=S, 40=E, 90=X
- rev: revision; sensor always P; no voids

## L13

- fixed-width text; the title, the header, dashed rules, PAGE lines and END OF REPORT are not records
- columns by character position (0-based, end exclusive): station 0-10, LST date 10-20, LST time HHMM 21-25,
- value 26-33 (right aligned), unit 34-36 (FT or M), quality 37-38 (G/S/E/X), revision 39-41
- sensor: always P; no voids

## L14

- text log; lines starting with NOTE are not records
- reading lines: `YYYY-MM-DD HH:MM:SSZ stn=<token> sensor=<P|B> gh=<value><ft|m> q=<code> rev=<n>`
- time: UTC
- void lines: `VOID stn=<token> sensor=<P|B> t=<YYYY-MM-DDTHH:MM:SSZ> rev=<n>` are void copies

## L15

- YAML: `blocks` is a list; each block has station, sensor (primary or backup), unit (ft or m) and rows
- each row is a flow sequence [epoch_seconds_utc, value, quality g/s/e/x, revision]
- scalars are text as written, quoted or not; no voids

## L16

- YAML: `stations` maps a station token to a mapping of UTC minute keys `YYYY-MM-DDTHH:MMZ` to readings
- a reading is a mapping v (value), u (unit ft or m), r (revision), in flow or block style
- a key whose value is a flow list holds several readings of that minute (one per revision)
- sensor: always P; quality: none (G); no voids

## L17

- JSON document: `meta.unit` is the default unit; `series` is a list of runs
- a run has site, sensor, start (UTC epoch seconds), step (seconds), rev, values and an optional unit that overrides meta.unit
- value k is at start + k x step; null is no record
- quality: none (G); no voids

## L18

- SQLite: table sites (sid, token) and table readings (sid, sensor, t_serial, value, unit, q, rev, void)
- t_serial: LST serial days in the 1900 system (H3)
- value: REAL in the unit of the unit column (FT or M); its decimal is the shortest text that
- round-trips the REAL
- q: G/S/E/X; void 1 marks a void copy (value NULL); records in rid order

## L19

- SQLite: table obs (stn, ts, gh_mm, sensor, rev, flag) and table voids (stn, ts, sensor, rev)
- ts: UTC epoch seconds
- gh_mm: millimetres
- flag: empty=G, S, E, X
- every voids row is a void copy; obs rows come first in record order

## L20

- csv with header `site,time_lst,gh_ft,source`
- time_lst: LST YYYY-MM-DD HH:MM
- gh_ft: feet
- sensor: always P; quality: none (G); revision 1; no voids

## Units and conversions

- ft = m / 0.3048, ft = cm / 30.48, ft = mm / 304.8, exactly (handbook H8).
- A record without its own unit takes the equipment register unit (handbook H8).

## Catalog

- file_order: processing order; files: file, layout, status (ARCHIVED files are absent).
- routes: route, file, site (station id), sensor, from_utc, to_utc, status (ACTIVE or RETIRED).

