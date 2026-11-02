# Folder index

Tier: contract.

This document names every file in this folder, states its tier and states its schema. It makes no statement about which file bears on which result.

## Tiers

| tier | meaning |
| --- | --- |
| contract | states a rule. Binding. |
| primary | a source record of work the house performed. |
| reference | a table of settings keyed by identifier and window. |
| correction | a stream of later statements about primary records. |
| observation | a log of what a machine or a person observed. |
| legacy | material that predates the contract and is retained. |
| illustrative | a reading kept for display that states nothing binding. |

## Contract documents

| file | content |
| --- | --- |
| `index.md` | this index |
| `conform_contract.md` | how a delivery timeline is rebuilt from source clip events |
| `timecode_spec.md` | the conversion between a written timecode and a frame count |
| `provenance_spec.md` | which source carries a measurement, and how the observation logs are read |
| `format_notes.md` | the written forms of the delimited files, the JSON streams and the configuration layers |
| `tape_layout.md` | the fixed width record layout of the tape index |
| `scenario_notes.md` | what a scenario is and which material it draws on |

## Event sources

Tier: primary. Comma separated with a header line. Field order and field meanings are in `format_notes.md`. Field ten of a row is the speed in parts per million and is primary; field nineteen is the same measurement as a percentage and is illustrative.

| file | content |
| --- | --- |
| `events_visible_a.csv` | first shard of the `visible` event set |
| `events_visible_b.csv` | second shard of the `visible` event set |
| `events_peak_a.csv` | first shard of the `peak` event set |
| `events_peak_b.csv` | second shard of the `peak` event set |
| `events_steady_a.csv` | first shard of the `steady` event set |
| `events_steady_b.csv` | second shard of the `steady` event set |
| `events_burst_a.csv` | first shard of the `burst` event set |
| `events_burst_b.csv` | second shard of the `burst` event set |
| `events_latency_a.csv` | first shard of the `latency` event set |
| `events_latency_b.csv` | second shard of the `latency` event set |

## Correction streams

Tier: correction. One JSON object per line with the keys `event_uid`, `revision`, `op`, `fields`, `recorded_at` and `source_system`.

| file | content |
| --- | --- |
| `corrections_visible_p1.jsonl` | first part of the `visible` correction stream |
| `corrections_visible_p2.jsonl` | second part of the `visible` correction stream |
| `corrections_peak_p1.jsonl` | first part of the `peak` correction stream |
| `corrections_peak_p2.jsonl` | second part of the `peak` correction stream |
| `corrections_steady_p1.jsonl` | first part of the `steady` correction stream |
| `corrections_steady_p2.jsonl` | second part of the `steady` correction stream |
| `corrections_burst_p1.jsonl` | first part of the `burst` correction stream |
| `corrections_burst_p2.jsonl` | second part of the `burst` correction stream |
| `corrections_latency_p1.jsonl` | first part of the `latency` correction stream |
| `corrections_latency_p2.jsonl` | second part of the `latency` correction stream |

## Override streams

Tier: correction. One JSON object per line with the keys `event_uid`, `field`, `value`, `approver`, `recorded_at` and `scope`. A file name carries the half year of the `recorded_at` of its records, and any stream may hold records for any scenario.

| file | content |
| --- | --- |
| `overrides_2025h1.jsonl` | overrides recorded in the first half of 2025 |
| `overrides_2025h2.jsonl` | overrides recorded in the second half of 2025 |
| `overrides_2026h1.jsonl` | overrides recorded in the first half of 2026 |
| `overrides_2026h2.jsonl` | overrides recorded in the second half of 2026 |

## Reference tables

Tier: reference. Header line present. Window columns follow section 4 of `format_notes.md`.

| file | key columns | payload columns |
| --- | --- | --- |
| `assets_gen_a.csv` | `canonical_code`, `generation` | `family_code`, `retired_at` |
| `assets_gen_b.csv` | `canonical_code`, `generation` | `family_code`, `retired_at` |
| `assets_gen_c.csv` | `canonical_code`, `generation` | `family_code`, `retired_at` |
| `alias_hops_vendor.tsv` | `vendor_key`, `valid_from`, `valid_to` | `house_code` |
| `alias_hops_house.tsv` | `house_code`, `valid_from`, `valid_to` | `target_code` |
| `rate_families.csv` | `family_code`, `valid_from`, `valid_to` | `rate_family`, `fps_num`, `fps_den`, `nominal_fps`, `drop_frame` |
| `cadence_map.tsv` | `site_code`, `source_family`, `delivery_family` | `num`, `den` |
| `handle_policy.tsv` | `event_class`, `site_code`, `valid_from`, `valid_to` | `handling` |
| `transition_matrix.csv` | `event_class`, `state_from`, `state_to` | `legality` |
| `authority_roles.csv` | `approver`, `field_scope`, `valid_from`, `valid_to` | `role` |
| `source_tiers.csv` | `source_system`, `valid_from`, `valid_to` | `tier` |
| `host_clock_offsets.csv` | `host`, `valid_from`, `valid_to` | `offset_minutes` |
| `delivery_exceptions.csv` | `scenario`, `timeline_id`, `action`, `effective_at` | `recurrence`, `until`, `weekday`, `time_of_day` |
| `nesting_edges.tsv` | `scenario`, `event_uid` | `required_timeline`, `declared_at` |

The two field columns above group each field by the part it plays, the key it is read by or the payload it carries. They state no written order. The written order of a delimited table is the header line of the file itself.

The three asset tables each hold one generation and together hold the asset register. `nesting_edges.tsv` is the only statement of the timeline a nest event requires.

## Configuration layers

Tier: contract for the settings they carry.

| file | content |
| --- | --- |
| `conform.ini` | sections of settings, with an `inherits` key on some sections |
| `site_overrides.ini` | sections that layer over `conform.ini` |
| `house.properties` | house wide settings, with the separator and continuation forms of `format_notes.md` |
| `scenario_cutoffs.json` | the cutoff instant and the excluded classes of each scenario, with a `defaults` object |
| `reason_codes.json` | the closed set of reason codes, each with a kind and a remedy |

## Observation logs

Tier: observation. Line oriented, read as `provenance_spec.md` states.

| file | content |
| --- | --- |
| `conform_host_a_prev.log` | the preceding rotation of the first ingest host group |
| `conform_host_a_curr.log` | the current rotation of the first ingest host group |
| `conform_host_b_prev.log` | the preceding rotation of the second ingest host group |
| `conform_host_b_curr.log` | the current rotation of the second ingest host group |
| `arbitration_notes.log` | the arbitration record of the conform house |

## Legacy material

| file | tier | content |
| --- | --- | --- |
| `tape_index_v1.txt` | legacy | the full tape room index, fixed width, laid out in `tape_layout.md` |
| `tape_index_v2.txt` | legacy | a partial rewrite of the tape room index, same layout |
| `reference_conform.py` | legacy | the conform engine the house ran before the contract was written |

The two tape index files remain the tape room measurements of the clips they cover, and `provenance_spec.md` states when they carry a measurement and which of the two counts.

In `reference_conform.py` only the stage list `STAGES` and the stage visit counter `profile` carry house sign off. Every frame count, phase, reason code and total that `legacy_run` computes carries none.
