# Feed layouts

Every reading shard carries canonical fields run token, sensor or channel token, instant, raw value, unit, rev and
void, written differently per layout. The catalog (ingest_catalog_*.json) names the layout of each file. Tokens
are resolved as the handbook says (H3, H6, H14). Unless stated otherwise a field is text and an empty field is
missing.

## Reading layouts

### L01 (csv, comma)
- header: run,sensor,ts_utc,raw,unit,rev,void
- ts_utc: ISO 8601 with Z. unit: ohm, kohm, V or mV.
- void: Y marks a void copy; empty otherwise. Missing value sentinel: NaN.

### L02 (tsv)
- header: RUN SERIAL EPOCH_S VALUE UNITS REVISION STATUS (tab separated)
- EPOCH_S: epoch seconds. UNITS: OHM, KOHM, VOLT or MVOLT.
- STATUS: VOID marks a void copy, VALID otherwise. Missing value sentinel: -9999.

### L03 (psv, pipe)
- header: run_tag|chan|local_time|isdst|reading|rev|flag
- chan: a channel token (resolved through the channel map at the reading instant).
- local_time: site wall time written DD/MM/YYYY HH:MM:SS; isdst as in handbook H4.2.
- reading: in the family's native unit, ohm for PRT and NTC, volt for DIODE.
- flag: x marks a void copy. Missing value sentinel: OVL.

### L04 (jsonl)
- keys: r (run), s (serial), t_ms (epoch milliseconds), v (raw as a string, null when missing), u (unit),
  rv (rev), del (true for a void copy).

### L05 (ndjson)
- keys: meta.run, meta.rev, sensor, at (ISO 8601 with the site offset), value.x (raw string), value.unit,
  void (1 for a void copy). Missing value sentinel: ERR.

### L06 (xml)
- readings/batch elements carry the run token; each r element carries s, t (ISO 8601 with Z), raw, u, rev and
  void (true or false). An empty raw is missing.

### L07 (sqlite)
- table readings(run, sensor, epoch, raw, unit, rev, voided). epoch is seconds; raw is TEXT; voided 1 marks a void
  copy; a NULL raw is missing.

### L08 (db, sqlite)
- table frames(frame_id, run, epoch_ms, rev, void) and table samples(frame_id, channel, micro).
- A sample belongs to its frame: the frame gives run, instant (epoch milliseconds), rev and void.
- channel is a channel token. micro is an integer in micro-ohm for PRT and NTC, micro-volt for DIODE; NULL is
  missing.

### L09 (yaml)
- a list of records with keys run, sensor, at (epoch seconds), raw (quoted string, null when missing), unit, rev,
  void (yes for a void copy, no otherwise).

### L10 (yml)
- a mapping from sensor token to a block with unit (one unit for the whole block) and samples, a list of strings
  "run | instant (ISO 8601 with Z) | raw | rev | void" where void is 1 for a void copy. A raw of - is missing.

### L11 (json)
- one document: units maps each sensor token to its unit; data holds parallel arrays run, sensor, t (ISO 8601 with
  the site offset), raw, rev and void (true for a void copy). An empty raw is missing.

### L12 (txt, fixed width)
- lines starting with # are comments; the header line RUN SENSOR UTC RAW REV V repeats every 50 records.
- columns: run (10 characters), sensor (11), UTC instant written YYYYMMDDTHHMMSSZ (17), raw with a unit suffix
  (15: R ohm, K kohm, V volt, M millivolt), rev (4), void flag (Y or N).
- Missing value sentinel: *****.

### L13 (md)
- one section per run (## Run <token>) with pipe tables | sensor | utc | raw | unit | rev | void |; long tables
  continue after a (continued) line with a repeated header. utc is YYYY-MM-DD HH:MM:SS in UTC. raw carries thousands
  separators (1,234.5678). void reads void for a void copy and is empty otherwise. Missing value sentinel: n/a.

### L14 (csv, semicolon)
- header: run;probe;time_local;isdst;value;unit;rev;cancelled
- time_local: site wall time YYYY-MM-DD HH:MM:SS with isdst as in H4.2. value uses a decimal comma (123,4567).
- cancelled: 1 marks a void copy. An empty value is missing.

### L15 (tsv)
- header: ch epoch_ms run val unit rev void
- ch: a channel token; epoch_ms: epoch milliseconds; val in kohm for PRT and NTC and in mV for DIODE.
- void: 1 marks a void copy. Missing value sentinel: NA.

### L16 (jsonl, blocks)
- one block per line: run, sensor, rev, t0 (ISO 8601 with Z), unit, dt (seconds after t0, one per sample),
  v (raw strings, null when missing) and void (the zero-based indices of void samples in the block).

## Link files

### S0 link catalog (csv)
- header: link,rev,effective_from,kind,status,description. effective_from is a date. status ACTIVE or VOID.

### S1 segments (xml)
- link elements (id, rev) hold seg elements: n (sequence from the hot end), mat (material token), len (with mm),
  area (an area spec, handbook H16.2) and lot (empty when none).

### S2 segments (psv)
- header: link|rev|seq|material|length|length_unit|area_spec|lot. length_unit mm, cm or in. lot - means none.

### J1 joints (jsonl)
- keys: link, rev, pos (0 is the hot end, n the cold end after segment n), class, bolts, torque (NOM or LOW, any
  case), indium (true, false, yes or no).

### I1 installs (tsv)
- header: run link hot cold state rev. state INSTALLED or REMOVED.

### A1 amendments (ndjson)
- keys: seq, link, rev, field, value, action (SET or REVERSE, any case), status (POSTED or PENDING, any case),
  reverses (the seq a REVERSE names), entered.

## Other files

### run log (csv)
- header: run,event,local_time,value,rev,entered_by. local_time is site wall time YYYY-MM-DD HH:MM.

### harness ledger (psv)
- header: bundle|run|node_hint|dissipation|unit|rev|void. unit mW (three places) or uW. void VOID marks a void row.

### intercept register (xml)
- intercept elements (id, run, band W or C, nominal_K) and bundle elements (id, run, node).

### lot certificates (xml)
- lot elements (id, k_scale, status CERTIFIED, PROVISIONAL or WITHDRAWN, issued).

### ruling addendum (xml)
- entry elements (seq, ref, action RESCIND or REINSTATE, status ISSUED or DRAFT).

### cooler service log (tsv)
- header: date cooler action value by. DERATE carries a percentage value; RESTORE carries none.

### channel map (db, sqlite)
- table channel_assignment(channel, serial, valid_from_utc, valid_to_utc); NULL valid_to_utc is open-ended.

### alias register (sqlite)
- tables material_alias(token, target, status), node_alias(token, node), link_alias(old_id, new_id, effective),
  sensor_relabel(old_serial, new_serial, effective_utc).

### sensor inventory (json), sensor map (yaml), campaign profile (yml), overlays (yaml), site calendar (yml)
- as written; keys are self-describing. Profile run entries are a list of mappings with an id key.

### workbook (xlsx)
- sheet names live in xl/workbook.xml and are bound to worksheet parts through xl/_rels/workbook.xml.rels; the part
  file names do not follow the sheet order. Cells are shared strings, inline strings or numbers, and a numeric value
  may be stored as text. The first row of each data sheet is its header.

### memo (pdf)
- Flate-compressed content streams; every cell is a separately positioned text object (Tm) and the objects of a page
  are not in reading order. Strings are literal, hexadecimal or TJ arrays. A row is the set of objects sharing a y
  coordinate, ordered by x. A table continues on the next page after a (continued) line that repeats its header.

## Field dictionary

| layout | source field | canonical field |
|---|---|---|
| A1 | seq | seq |
| A1 | link | link_token |
| A1 | rev | rev |
| A1 | field | field |
| A1 | value | value |
| A1 | action | action |
| A1 | status | status |
| A1 | reverses | target_seq |
| A1 | entered | instant_iso_z |
| I1 | run | run_token |
| I1 | link | link_token |
| I1 | hot | node_token |
| I1 | cold | node_token |
| I1 | state | state |
| I1 | rev | rev |
| J1 | link | link_token |
| J1 | rev | rev |
| J1 | pos | joint_position |
| J1 | class | joint_class |
| J1 | bolts | bolts |
| J1 | torque | torque |
| J1 | indium | indium |
| L01 | run | run_token |
| L01 | sensor | serial_token |
| L01 | ts_utc | instant_iso_z |
| L01 | raw | raw |
| L01 | unit | unit |
| L01 | rev | rev |
| L01 | void | void |
| L02 | RUN | run_token |
| L02 | SERIAL | serial_token |
| L02 | EPOCH_S | instant_epoch_s |
| L02 | VALUE | raw |
| L02 | UNITS | unit |
| L02 | REVISION | rev |
| L02 | STATUS | void |
| L03 | run_tag | run_token |
| L03 | chan | channel_token |
| L03 | local_time | instant_local_dmy |
| L03 | isdst | offset_selector |
| L03 | reading | raw_native |
| L03 | rev | rev |
| L03 | flag | void |
| L04 | r | run_token |
| L04 | s | serial_token |
| L04 | t_ms | instant_epoch_ms |
| L04 | v | raw |
| L04 | u | unit |
| L04 | rv | rev |
| L04 | del | void |
| L05 | meta.run | run_token |
| L05 | meta.rev | rev |
| L05 | sensor | serial_token |
| L05 | at | instant_iso_offset |
| L05 | value.x | raw |
| L05 | value.unit | unit |
| L05 | void | void |
| L06 | batch@run | run_token |
| L06 | r@s | serial_token |
| L06 | r@t | instant_iso_z |
| L06 | r@raw | raw |
| L06 | r@u | unit |
| L06 | r@rev | rev |
| L06 | r@void | void |
| L07 | readings.run | run_token |
| L07 | readings.sensor | serial_token |
| L07 | readings.epoch | instant_epoch_s |
| L07 | readings.raw | raw |
| L07 | readings.unit | unit |
| L07 | readings.rev | rev |
| L07 | readings.voided | void |
| L08 | frames.run | run_token |
| L08 | frames.epoch_ms | instant_epoch_ms |
| L08 | frames.rev | rev |
| L08 | frames.void | void |
| L08 | samples.channel | channel_token |
| L08 | samples.micro | raw_micro |
| L08 | samples.frame_id | frame_link |
| L09 | run | run_token |
| L09 | sensor | serial_token |
| L09 | at | instant_epoch_s |
| L09 | raw | raw |
| L09 | unit | unit |
| L09 | rev | rev |
| L09 | void | void |
| L10 | <key> | serial_token |
| L10 | unit | unit |
| L10 | samples[0] | run_token |
| L10 | samples[1] | instant_iso_z |
| L10 | samples[2] | raw |
| L10 | samples[3] | rev |
| L10 | samples[4] | void |
| L11 | data.run | run_token |
| L11 | data.sensor | serial_token |
| L11 | data.t | instant_iso_offset |
| L11 | data.raw | raw |
| L11 | units[sensor] | unit |
| L11 | data.rev | rev |
| L11 | data.void | void |
| L12 | RUN | run_token |
| L12 | SENSOR | serial_token |
| L12 | UTC | instant_compact_z |
| L12 | RAW | raw_with_suffix |
| L12 | REV | rev |
| L12 | V | void |
| L13 | ## Run | run_token |
| L13 | sensor | serial_token |
| L13 | utc | instant_utc_space |
| L13 | raw | raw_thousands |
| L13 | unit | unit |
| L13 | rev | rev |
| L13 | void | void |
| L14 | run | run_token |
| L14 | probe | serial_token |
| L14 | time_local | instant_local_iso |
| L14 | isdst | offset_selector |
| L14 | value | raw_decimal_comma |
| L14 | unit | unit |
| L14 | rev | rev |
| L14 | cancelled | void |
| L15 | ch | channel_token |
| L15 | epoch_ms | instant_epoch_ms |
| L15 | run | run_token |
| L15 | val | raw_milli_kilo |
| L15 | unit | unit |
| L15 | rev | rev |
| L15 | void | void |
| L16 | run | run_token |
| L16 | sensor | serial_token |
| L16 | rev | rev |
| L16 | t0 | block_start_iso_z |
| L16 | dt | offset_seconds |
| L16 | v | raw |
| L16 | unit | unit |
| L16 | void | void_indices |
| S0 | link | link_token |
| S0 | rev | rev |
| S0 | effective_from | date |
| S0 | kind | kind |
| S0 | status | status |
| S0 | description | text |
| S1 | link@id | link_token |
| S1 | link@rev | rev |
| S1 | seg@n | seq |
| S1 | seg@mat | material_token |
| S1 | seg@len | length_mm_suffix |
| S1 | seg@area | area_spec |
| S1 | seg@lot | lot |
| S2 | link | link_token |
| S2 | rev | rev |
| S2 | seq | seq |
| S2 | material | material_token |
| S2 | length | length |
| S2 | length_unit | length_unit |
| S2 | area_spec | area_spec |
| S2 | lot | lot |
