# Provenance specification

Tier: contract.

This document states which source carries a measurement when two sources carry it, and how the observation logs are read. The conform contract in `conform_contract.md` defers to this document on both questions.

## 1. Ingest logs

The ingest logs are `conform_host_a_prev.log`, `conform_host_a_curr.log`, `conform_host_b_prev.log` and `conform_host_b_curr.log`.

Each host group writes to a single file and rotates it. A file whose name ends `_prev.log` holds the rotation that preceded the file of the same host group whose name ends `_curr.log`. The reading order of the ingest logs is every `_prev.log` file first, then every `_curr.log` file, and within a file top to bottom. The last `INGEST` line that names a uid in that reading order carries the recorded time of the event. Timestamps inside a file need not increase, and a timestamp in a `_prev.log` file may stand later than the timestamp of the same uid in a `_curr.log` file.

A log record occupies one line that begins with a timestamp. A line that begins with whitespace is a continuation of the record above it and carries no record of its own, whatever tokens it holds.

A record line is laid out as a timestamp, then the host, then the record kind, then space separated tokens of the form name equals value. Only records of kind `INGEST` bear on the recorded time, and only through their `uid` token.

## 2. Host clocks

Log timestamps are host local wall clock readings written as a date, a space, and a time of day. They carry no zone marker.

`host_clock_offsets.csv` carries, for each host and each window, the number of minutes by which that host local reading stands ahead of UTC. A reading converts to UTC by subtracting that number of minutes. The window that applies to a reading is the window of that host whose `valid_from` is at or before the reading and whose `valid_to` is after it, comparing the reading against the written window bounds directly. A host appears with a changed offset across the year, and the window that contains a reading is the only window that bears on it.

## 3. Tape measurements and the cutover

`tape_index_v1.txt` and `tape_index_v2.txt` hold the tape room measurements of source clips, keyed by tape key. `tape_layout.md` states their record layout.

For one event, the tape index carries an entry when field twenty of the event row is a non empty tape key and a record for that key exists. Where both files carry a record for a key, the record in `tape_index_v2.txt` is the one that counts and the record in `tape_index_v1.txt` is superseded.

The tape index is the source of the in timecode, the out timecode and the speed of an event when the effective time of the event stands before the `tape_cutover_utc` setting of the scenario and the tape index carries an entry for the event. In every other case those three measurements come from the event row, which `tape.key.blank.policy` in `house.properties` also records for the case of an empty tape key.

The tape index states speed in parts per billion, where one billion is unity. The event row states speed in parts per million, where one million is unity. The conform contract reads speed in parts per million.

Corrections and overrides act on the event row. Where the tape index is the source of a measurement under this section, a correction or an override to that measurement on the event row leaves the conform value unchanged.

## 4. Correction ties

`arbitration_notes.log` holds the arbitration record of the conform house. Each record of kind `ARBITRATION` names a case, an event uid, a revision, a left side and a right side each with a source system and a tier and a recorded time, and the winning source system. A record whose winner token reads `none` is a case the house declined to settle.

The log is the statement of how a tie between two correction records at the same highest revision settles. The tiers the log quotes are the tiers `source_tiers.csv` carries for those source systems in the window containing the quoted recorded time. A tie of a shape the log settles consistently settles the same way in this run. A tie of a shape the log declines to settle yields the reason code `TIE_UNRESOLVED`.

A line that begins with whitespace is a continuation of the record above it.

## 5. Order of authority

Where two statements bear on one value, the earlier entry in this list is the one that counts.

1. `conform_contract.md`, `timecode_spec.md`, this document, `format_notes.md` and `tape_layout.md`.
2. `house.properties`, `scenario_cutoffs.json`, `site_overrides.ini` and `conform.ini` for the settings they carry.
3. The override streams, for a field an override applies to.
4. The correction streams, for a field the applying correction names.
5. The tape index, for the three measurements named in section 3 while the effective time stands before the cutover.
6. The event row.
7. `reference_conform.py`, which carries house sign off for its stage list and its stage visit counter and for nothing else.
