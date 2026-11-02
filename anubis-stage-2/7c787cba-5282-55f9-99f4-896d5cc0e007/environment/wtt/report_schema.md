# Compile output schema

The compile writes eighteen documents into its output directory and nothing
else. Twelve are JSON, six are text. Every JSON document is one object
serialized with sorted keys, two space indentation and a trailing newline.
Every delimited document carries the header line shown, one row per key in the
stated order, no quoting, a single newline between rows and one at the end.

Dates are `YYYY-MM-DD`. Instants are `YYYY-MM-DDTHH:MM:SSZ`. Every count and
every minute figure is a JSON integer.

## identity_resolution.json

Keys: `alias_row_count`, `canonical_path_count`, `malformed_spellings`,
`rejected_cycle_members`, `resolved_through_alias_count`,
`unresolved_spellings`.

`canonical_path_count` counts the register rows whose identifier does not sit
on a cycle. `alias_row_count` counts the rows of `path_alias_map.csv`.

The two spelling lists and the alias count are drawn from one pool: the
distinct values of the `path` column of `exception_dates.csv` together with the
distinct non empty values of the `variant_of` column of `path_register.csv`.
`resolved_through_alias_count` counts the spellings of that pool whose
resolution took at least one alias move and landed on a registered path.
`malformed_spellings` is the sorted list of the spellings of that pool that
fail canonicalisation. `unresolved_spellings` is the sorted list of the
spellings of that pool that canonicalise and whose walk then resolves to
nothing. `rejected_cycle_members` is the sorted list of canonical identifiers
that sit on a cycle, which is the one list drawn from the alias map and the
register rather than from that pool.

## authority_resolution.json

Keys: `fields`, `superseded_file_count`.

`fields` is a list of five objects, sorted by `field`, each with `field`,
`source_of_record` and `divergence_count`. The field names are
`departure_window`, `operator_rank_weight`, `recurrence_rule`,
`section_headway` and `zone_transition`. `source_of_record` is the bare file
name of the file of record, taken from this table, because two files can hold
a role in one field and only one of them is named:

| field | source_of_record |
|---|---|
| `departure_window` | `path_register.csv` |
| `operator_rank_weight` | `operator_register.html` |
| `recurrence_rule` | `recurrence_rules.json` |
| `section_headway` | `wtt_mailbox.mbox` |
| `zone_transition` | `zone_transitions.csv` |

`superseded_file_count` counts the files `file_role_index.md` gives the
superseded role, which is four.

## expansion_audit.json

Keys: `paths`, `rules_with_empty_selection`, `selected_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `rule_id`, `period_count`, `candidate_count`, `selected_count`,
`first_selected` and `last_selected`. `candidate_count` is the total size of
every period's candidate set. `first_selected` and `last_selected` are dates, or
null when the path selected nothing. `rules_with_empty_selection` is the sorted
list of rule identifiers that selected nothing for at least one path that names
them. `selected_total` sums `selected_count`.

## exception_merge.json

Keys: `paths`, `dropped_addition_total`, `cap_bound_paths`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `excluded_count`, `added_count`, `dropped_addition_count`,
`pre_cap_count`, `cap`, `post_cap_count`, `in_window_count`, `first_in_window`
and `last_in_window`. `excluded_count` counts the exclusion dates that removed a
date that was there. `added_count` counts the additions that put a date into the
sequence that was not already in it.
`cap` is the rule's `limit`. The two date fields are null when the window holds
nothing. `dropped_addition_total` sums `dropped_addition_count`.
`cap_bound_paths` is the sorted list of path identifiers whose cap dropped at
least one date.

## overlay_resolution.json

Keys: `edge_count`, `paths`, `rejected_cycle_paths`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `chain_root`, `chain_depth`, `lost_day_count` and `kept_day_count`.
A rejected path has a `chain_root` of its own identifier, a `chain_depth` of 0,
a `kept_day_count` of 0 and a `lost_day_count` equal to the day count it
entered the stage with. `edge_count` counts the base and variant edges.
`rejected_cycle_paths` is the sorted list of identifiers rejected for a variant
cycle.

## timepoint_materialization.json

Keys: `fold_count`, `gap_count`, `midnight_crossing_count`, `movement_total`,
`paths`, `shifted_minute_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `movement_count`, `first_departure_utc` and `last_departure_utc`.
The two instant fields are null when the path has no movement. `gap_count` and
`fold_count` count movements whose departure resolved through a gap and through
a fold. `shifted_minute_total` sums the gap lengths in minutes over the gap
movements. `midnight_crossing_count` counts movements whose last section entry
falls on a later local date than the service date, measured in the path's zone
at the offset in force at that entry instant. `movement_total` sums
`movement_count`.

## headway_resolution.json

Keys: `admitted_total`, `deferral_histogram`, `deferred_total`,
`section_admitted_counts`, `withheld_total`.

`deferral_histogram` is an object whose keys are the deferral counts as decimal
strings from `0` up to the maximum, each mapping to the number of admitted
movements that took that count. `section_admitted_counts` maps every section
identifier in `section_register.csv` to the number of admitted entry instants
on it. `deferred_total` counts admitted movements whose count was above zero.

## withheld_paths.json

Keys: `movements`, `rejected_paths`.

`movements` is a list sorted by `path_id` then `service_date`, one object per
withheld movement, with `path_id`, `service_date` and `reason`. The only reason
a movement carries is `headway`. `rejected_paths` is a list sorted by
`path_id`, one object per rejected path, with `path_id` and `reason`, where the
reason is `variant_cycle`.

## compiled_timetable.json

Keys: `admitted_movement_total`, `path_minutes_total`, `paths`,
`withheld_movement_total`.

`paths` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `operator_id`, `zone_id`, `route_id`, `admitted_day_count`,
`deferred_day_count`, `withheld_day_count`, `deferral_minute_total` and
`path_minutes`.

## canonical_calendars.json

Keys: `calendars`, `set_bit_total`.

`calendars` is a list sorted by `path_id`, one object per registered path, with
`path_id`, `base_day`, `bit_length` and `hex`. `set_bit_total` sums the set
bits over every calendar.

## timetable_digest.json

Keys: `digest`, `leading_terms`, `modulus`, `term_count`.

`modulus` is 2147483647. `term_count` counts the paths the digest ran over.
`leading_terms` is a list of the first three terms in position order, each an
object with `position`, `value` and `term`. A compile with fewer than three
paths lists as many as it has.

## data_quality.json

Keys: `issue_counts`, `issue_total`, `subjects`.

`issue_counts` maps every one of the seven codes below to a count, with a zero
entry when the code did not fire. `subjects` maps every one of the seven codes
to a sorted list of the subjects that raised it, empty when none did.
`issue_total` sums the counts.

| code | subject | raised when |
|---|---|---|
| `ALIAS_CYCLE` | canonical identifier | the identifier sits on an alias cycle |
| `CAP_BINDING` | path identifier | the rule cap dropped at least one date |
| `EMPTY_CALENDAR` | path identifier | the path has no admitted date |
| `FOLD_DEPARTURE` | path identifier | at least one departure resolved through a fold |
| `HEADWAY_WITHHELD` | path identifier | at least one movement was withheld |
| `UNRESOLVED_SPELLING` | spelling as written | the spelling is malformed or its walk failed |
| `VARIANT_CYCLE` | path identifier | the path sits on a variant cycle |

## operator_rollup.tsv

Tab separated. Header
`operator_id	rank_weight	path_count	admitted_movements	withheld_movements	path_minutes`.
One row per operator in `operator_register.html`, sorted by `operator_id`.

## section_rollup.psv

Pipe separated. Header
`section_id|section_class|zone_id|min_headway_min|admitted_entries`. One row per
section, sorted by `section_id`. `min_headway_min` is the value in force after
stage 2.

## path_rollup.csv

Comma separated. Header
`path_id,operator_id,rule_id,admitted_days,deferred_days,withheld_days,path_minutes`.
One row per registered path, sorted by `path_id`.

## flagged_paths.xml

One `flagged` element carrying a `count` attribute and one `path` child per flag
with an `id` attribute and a `reason` attribute, sorted by identifier then
reason. The five reasons are `cap_binding`, `empty_calendar`,
`fold_departure`, `gap_departure` and `variant_cycle`, raised on the same
conditions as the matching data quality codes, with `gap_departure` raised when
at least one departure of the path resolved through a gap. `count` is the number
of `path` children. The document is written with the XML declaration line
`<?xml version="1.0" encoding="utf-8"?>`, then the `flagged` element, then a
trailing newline.

## compile_report.md and run_status.txt

These two carry the line shapes the shipped reporting code already writes, and
this repair leaves those shapes alone. Read them off that code. The figures they
carry are the ones the stages above produce.
