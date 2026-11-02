# Report schema

Every delivered document is a JSON object. This file fixes the field names, the value types and the
array orderings. It carries no derived value.

## Workspace lock plan

One document per workspace of the workspace manifest.

| field | type |
| --- | --- |
| `workspace` | string |
| `snapshot_day` | integer |
| `copyleft` | string, `allowed` or `forbidden` |
| `footprint_bytes` | integer |
| `package_count` | integer |
| `quarantined_records` | integer |
| `packages` | array of objects, ascending `package` |

Each entry of `packages` carries `package` (the reported name) as a string, `version` as a
major.minor.patch string, `features` as the integer enabled feature mask, `licence_family` as the
string `permissive` or `copyleft`, and `bytes` as the integer artifact bytes of the locked version.

## Registry performance report

| field | type |
| --- | --- |
| `shards_decoded` | integer |
| `blocks_decoded` | integer |
| `records_decoded` | integer |
| `dependency_entries_decoded` | integer |
| `decoded_bytes` | integer |
| `excluded_bytes` | integer |
| `locked_bytes` | integer |
| `byte_residual` | integer |
| `workspaces_resolved` | integer |
| `footprint_by_workspace` | object keyed by workspace name with integer members |
| `recovered_parameters` | object |

The counts cover the field shards only. `recovered_parameters` carries `salt` as a string,
`window_span`, `bias_limit`, `rotation_base` and `quarantine_days` as integers, and
`permutation_multiplier` as a string of `0x` and eight lowercase hexadecimal digits.

## Bottleneck analysis

| field | type |
| --- | --- |
| `workspaces` | array of objects, ascending `workspace` |

Each entry carries `workspace` as a string, `held_back` as an array of objects in ascending
`package`, each carrying `package`, `locked` and `newest_eligible` as strings, and
`permissive_packages` and `copyleft_packages` as arrays of reported names in ascending order that
together list every locked package of the workspace by governing family.

## Index integrity report

| field | type |
| --- | --- |
| `total_shards` | integer |
| `shards_with_full_flag_set` | integer, shards whose flag word is 0x07ff |
| `records_yanked` | integer, yanked records of registered packages |
| `records_deprecated` | integer, records carrying the deprecated marker |
| `records_unregistered_package` | integer |
| `dependency_entries_back_referenced` | integer, entries that arrived as a tag above 0 |
| `dependency_entries_unregistered_target` | integer |
| `excluded_bytes_by_cause` | object with integer members `unregistered_package` and `yanked` |

Every figure covers the field shards only.

## Derivation record

| field | type |
| --- | --- |
| `candidates` | array of objects, in the order the candidates were weighed |
| `falsifier_totals` | object keyed by falsifier label with integer members |
| `calibration_table` | array of objects, in published control order |
| `settlement_passes_by_workspace` | object keyed by workspace name with integer members |
| `licence_divergence` | array of workspace names, ascending |

Each entry of `candidates` carries `parameter` as one of `salt`, `window_span`, `bias_limit`,
`rotation_base`, `permutation_multiplier` and `quarantine_days`, `value` as a string written the way
the candidate lists write it, `verdict` as `accepted` or `rejected`, and `falsifier` as a falsifier
label, or `none` for an accepted candidate. Each entry of `calibration_table` carries `control` and
`figure` as strings and `published` and `reproduced` as integers.
