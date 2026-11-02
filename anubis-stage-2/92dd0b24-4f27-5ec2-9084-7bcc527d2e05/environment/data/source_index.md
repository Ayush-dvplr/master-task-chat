# Circuit Feed Index

Every file shipped under `/app/data` is listed here with the system that
produced it, its format, its provenance tier and its field order. Where a feed
carries a header row, that row is the authority on its field order. Tiers rank
as contract, primary source, reference table, correction stream, observation
log, legacy and illustrative. A higher tier governs a lower one only where the
slate contract says so.

## Contract tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `slate_window.ini` | circuit secretary | ini | sections `slate`, `stage_closes`, `tier_bands`, `penalty_weights` |
| `format_rules.ini` | rules committee | ini | base section `circuit`, one section per format, per stage override sections, `inherits` keys |
| `channel_policy.ini` | arbiter operations | ini | sections `channels`, `headers`, `scopes` |
| `source_registry.ini` | data governance | ini | one section per feed with `tier`, `charge_unit`, `decimal_mark`, `region`, `implied_places`, `charge_field` |
| `scenario_brief.ini` | tournament office | ini | sections `alpha`, `beta`, `mode` with a `basis` and its parameter |

## Primary source tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `entry_header_01.csv` | intake lane A | csv | submission id, handle, format, venue of play, local entry time, venue of record, source tag |
| `entry_header_02.csv` | intake lane B | csv | as lane A |
| `entry_header_03.csv` | intake lane C | csv | as lane A |
| `entry_header_04.csv` | intake lane D | csv | as lane A |
| `deck_lines_01.csv` | list capture, stage one | csv | submission id, row number, printed name, set code, copies |
| `deck_lines_02.csv` | list capture, stage two | csv | as above |
| `deck_lines_03.csv` | list capture, stage three | csv | as above |
| `deck_lines_04.csv` | list capture, stage four | csv | as above |
| `deck_lines_05.csv` | list capture, stage five | csv | as above |
| `deck_lines_06.csv` | list capture, stage six | csv | as above |
| `intake_journal.log` | intake receipt lane | log | timestamp, host, receipt id, submission, lane, with indented continuations |
| `intake_journal.log.1` | intake receipt lane, previous rotation | log | as above |
| `standing_entries.csv` | club registrar | csv | standing id, entrant handle, format, venue, weekday, local time, start date, until date, recorded at |
| `registry_seed.json` | arbiter operations | json | slate id, page size, empty page interval, listing lag, deferred format, contested feed, pre seeded entries, initial state |
| `service_token.json` | arbiter operations | json | token, request budget, renewal path, scopes, expiry code |

## Reference table tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `player_registry.csv` | membership office | csv | player id, display name, joined at, home venue, standing |
| `printing_registry.csv` | card database | csv | printing id, canonical key, set code, printed name, released on |
| `printing_release_board.txt` | card database, print shop view | txt | fixed width, printing id, canonical key, set code, released on, base charge |
| `venue_clocks.ini` | venue operations | ini | one section per venue with `base_offset_minutes` and `intake_host` |
| `venue_offset_shifts.csv` | venue operations | csv | venue, shift instant in UTC, offset before, offset after, source note |
| `venue_roster.csv` | regional office | csv | venue, region, effective at, recorded at |
| `host_clock_offsets.csv` | lane telemetry | csv | host, date, offset seconds |
| `stage_calendar.csv` | tournament office | csv | stage, venue, window start, window end, revision, published at |
| `authority_roster.csv` | judge programme | csv | judge, rank, effective at, recorded at |
| `format_exemptions.csv` | rules committee | csv | format, stage, canonical key, kind, recorded at |
| `contested_entries.csv` | circuit registrar | csv | submission id, revision note |

## Correction stream tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `global_restrictions_01.jsonl` | rules committee, first recording wave | jsonl | revision id, format, canonical key, allowed copies, point charge, supersedes, retracted, effective at, recorded at |
| `global_restrictions_02.jsonl` | rules committee, second recording wave | jsonl | as above |
| `global_restrictions_03.jsonl` | rules committee, third recording wave | jsonl | as above |
| `global_restrictions_04.jsonl` | rules committee, fourth recording wave | jsonl | as above |
| `addendum_north.csv` | northern regional office | csv | format, canonical key, allowed copies, point charge pts, effective at, recorded at |
| `addendum_south.csv` | southern regional office | csv | as above |
| `addendum_east.csv` | eastern regional office | csv | as above |
| `event_rider.tsv` | event organiser | tsv | format, canonical key, allowed copies, point charge cpt, authority, effective at, recorded at |
| `card_renames.csv` | card database corrections | csv | canonical key, printed name, effective at, recorded at |
| `reprint_links.tsv` | card database consolidations | tsv | link id, format, key a, key b, effective at, recorded at |
| `handle_changes.csv` | membership office corrections | csv | handle, player id, effective at, recorded at |
| `identity_events.csv` | membership office | csv | event id, kind, primary player, secondary player, effective at, recorded at |
| `amendments_01.jsonl` | list amendment desk, first file | jsonl | amendment id, submission id, version, status, lines, effective at, recorded at |
| `amendments_02.jsonl` | list amendment desk, second file | jsonl | as above |
| `entry_events_01.jsonl` | tournament office, first file | jsonl | event id, kind, submission id, successor, effective at, recorded at |
| `entry_events_02.jsonl` | tournament office, second file | jsonl | as above |
| `entry_exceptions.csv` | club registrar | csv | exception id, kind, standing id, venue, date, recorded at |
| `reinstatement_grants.csv` | judge programme | csv | grant id, player id, effective at, recorded at, granting judge |

## Observation log tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `judge_log_a.log` | head judge console A | log | timestamp, judge, stage, submission, governed by, points cpt, verdict, carry after |
| `judge_log_b.log` | head judge console B | log | as console A |

## Legacy tier

| File | Producer | Format | Fields |
| --- | --- | --- | --- |
| `legacy_entries.tsv` | retired circuit management system | tsv | season, submission id, handle, format, venue, local entry time, recorded at, note |

## Service

The arbiter at `/app/service/arbiter.py` and the console at
`/app/service/arbiterctl.py` ship with the environment. Their protocol is
described in `api_contract.md`.

## Illustrative tier

`legacy_floor_runbook.md` records floor habits from previous seasons and
settles nothing. `rules_committee_notes.md` carries errata against named
sections of the slate contract.
