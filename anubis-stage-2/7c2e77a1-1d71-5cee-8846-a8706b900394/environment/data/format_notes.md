# Format notes

Tier: contract.

This document records the written forms used by the delimited files, the JSON streams and the configuration layers of this folder.

## 1. Event shard files

The ten event shard files carry a header line and then one record per line in comma separated form with the standard quoting of that form. Fields are identified by position. Positions below are one based and match the field numbers the conform contract uses.

| field | title | content |
| --- | --- | --- |
| 1 | event_uid | the event identifier |
| 2 | timeline_id | the timeline the event belongs to |
| 3 | event_seq | the sequence number of the event inside its timeline |
| 4 | asset_ref | the vendor form of the asset reference |
| 5 | generation | the asset generation |
| 6 | source_in_tc | the in timecode |
| 7 | source_out_tc | the out timecode |
| 8 | head_handle | the head handle in frames |
| 9 | tail_handle | the tail handle in frames |
| 10 | rate_adjust | the speed in parts per million |
| 11 | event_class | the event class |
| 12 | state_from | the state the event leaves |
| 13 | state_to | the state the event enters |
| 14 | effective_at | the instant the event takes effect |
| 15 | recorded_at | the instant the event reached the system |
| 16 | source_system | the system that filed the event |
| 17 | offset_frames | a frame offset applied to the out frame count |
| 18 | ingest_host | the host that ingested the event |
| 19 | rate_adjust | the speed as a percentage |
| 20 | tape_key | the tape key, empty when the clip has no tape |
| 21 | revision | the revision of the event row |
| 22 | site_code | the conform site |
| 23 | notes | free text |

Fields ten and nineteen carry the same title. Field ten is a whole number of parts per million. Field nineteen is a percentage written with a comma for the decimal mark and is quoted on that account; it is kept for the operator display and is listed as illustrative in `index.md`.

Field seventeen is a whole number of frames and may be negative. A negative value is written inside round brackets, so `(12)` is negative twelve. Field eight and field nine are whole numbers of frames and are never negative.

Field twenty is empty when the clip has no tape. Fields fourteen and fifteen are instants written as a date, the letter T, a time of day and the letter Z.

## 2. Correction streams

Each line of a correction stream is one JSON object with the keys `event_uid`, `revision`, `op`, `fields`, `recorded_at` and `source_system`. The `op` value is `amend` or `delete`. The `fields` value is an object whose keys name event fields and whose values replace them. A `delete` record carries an empty `fields` object.

The field names the `fields` object uses map to event fields as follows.

| name in `fields` | event field |
| --- | --- |
| head_handle | field 8 |
| tail_handle | field 9 |
| rate_adjust_ppm | field 10 |
| offset_frames | field 17 |
| source_in_tc | field 6 |
| source_out_tc | field 7 |
| state_to | field 13 |
| site_code | field 22 |
| tape_key | field 20 |

Values for `head_handle`, `tail_handle`, `rate_adjust_ppm` and `offset_frames` are JSON numbers and are already whole frames or whole parts per million; they do not use the bracket form of section 1. Values for the remaining names are JSON strings.

Lines within a correction stream are in no particular order, and the two streams of a scenario are two parts of one stream.

## 3. Override streams

Each line of an override stream is one JSON object with the keys `event_uid`, `field`, `value`, `approver`, `recorded_at` and `scope`. The `field` value is one of `head_handle`, `tail_handle`, `rate_adjust_ppm`, `offset_frames` and `site_code`, and maps to an event field exactly as in section 2. The `scope` value is `event` or `timeline` and is recorded for the audit trail; it bears on nothing in the conform contract.

An override stream file name carries the half year of the `recorded_at` of the records it holds. Any stream may hold records for any scenario, and a scenario reads all four streams.

## 4. Delimited reference tables

Files with the suffix `.csv` are comma separated with a header line. Files with the suffix `.tsv` are tab separated with a header line. No reference table quotes a field.

Every reference table that carries `valid_from` and `valid_to` columns states a window that includes its `valid_from` instant and excludes its `valid_to` instant. Windows for one key do not overlap, and a key may have no window covering a given instant.

## 5. Configuration layers

`conform.ini` and `site_overrides.ini` hold sections introduced by a name in square brackets, then lines of the form name, equals sign, value. A line whose first character is a hash or a semicolon is a comment.

`house.properties` holds lines of the form name, separator, value, where the separator is an equals sign or a colon, each optionally surrounded by spaces. A line whose value ends with a backslash continues on the next line, and the continuation is joined to it after its leading spaces are dropped. A line whose first character is a hash is a comment.

`scenario_cutoffs.json` and `reason_codes.json` are JSON documents.

## 6. Observation logs

The ingest logs and `arbitration_notes.log` are line oriented. A line that begins with a timestamp starts a record. A line that begins with whitespace continues the record above it. `provenance_spec.md` states how they are read.
