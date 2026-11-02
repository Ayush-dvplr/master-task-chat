# Report contract

This document fixes the layout of every report down to the column order and the
order of every list. The other documents decide what each value means.

## Conventions

An absolute instant is written in basic UTC form, `YYYYMMDDTHHMMSSZ`. A wall
clock value is written in basic local form with no suffix, `YYYYMMDDTHHMMSS`.
Every minute, second, count, rank, revision, cent and debt value is an integer.
A value described as minutes between two instants is the whole number of
minutes rounded down toward negative infinity, so minus ninety seconds is minus
two minutes. An attendee is written as a registered identifier, an office as
its code, a collection as its id and a zone as its own `TZID`. An occurrence
identifier is the collection id, a colon, the UID, a colon and the original
instant, such as `cal-alpha:HX-WEEKLY-OPS-2027:20270113T163000Z`.

## Serialisation

A JSON report is one document with object keys sorted at every level, the
separators `,` and `:` with no spaces, every non ASCII character written as a
`\u` escape, and exactly one trailing line feed. A JSON lines report holds one
such object per line, each line ending in a line feed.

A table report (`.csv` comma, `.tsv` tab, `.psv` pipe) starts with one header
row naming its columns in the order given below, and every row, the header
included, ends in a line feed. A field is enclosed in double quotes when it
contains the delimiter, a double quote, a carriage return or a line feed, and
a double quote inside such a field is written twice; no other field is quoted.
A boolean is `true` or `false`, an absent value is an empty field, and a list
is its items joined with `;`.

## The reports, in manifest order

1. `decisions.jsonl`: one object per merge key, ordered by collection id, then
   UID, then raw recurrence identifier, each compared as a string. Keys:
   `collection`, `uid`, `recurrence_id` (the raw value, empty for a master),
   `href`, `winner` and `loser` (`local` or `server`; `loser` is empty for a
   key held by one replica that survives; for a tombstoned key the winner is
   the deleting replica and the loser the holding one), `rule` (`sole-replica`,
   `sequence`, `last-modified`, `revision`, `authority` or `tombstone`),
   `winning_sequence` (minus one for a tombstoned key) and `losing_sequence`
   (minus one when there is no losing component).
2. `reconciliation.json`: `policy` (the `conflict_policy` string of the
   store index), `effective_revision`, `counts` and `duplicate_uids`.
   `counts` holds `components`, the number of merged
   components, which is the number of merge keys that are not tombstoned;
   `contested`, the keys held by both replicas; `sole_replica`, the keys held by
   one replica that are not tombstoned; and `tombstoned`, the tombstoned keys.
   `duplicate_uids` holds one object per UID held by more than one collection after
   the merge, ordered by UID, with `uid`, `collections` (in collection priority
   order) and `primary_collection`.
3. `outbox_replay.jsonl`: one object per replayed operation in increasing
   `op_seq`, with `op_seq`, `collection`, `uid`, `recurrence_id`, `op`, `field`
   (empty for a `DELETE`), `outcome` and `sequence_after` (an integer or null).
4. `occurrences.csv`: columns `occurrence_id`, `collection`, `uid`, `office`,
   `original_utc`, `start_utc`, `end_utc`, `duration_seconds`,
   `duration_source` (`DTEND`, `DURATION`, `RDATE` or `DEFAULT`),
   `applied_shift_minutes`, `override`, `local_start`, `local_end` (in the zone
   of `office`), `utc_offset_minutes` (in force at the start in that zone),
   `solar_minutes`, `solar_in_window`, `series_class`, `required_attendees`
   and `summary`. `override` is `true` when the occurrence is the target of an
   applied override and `false` otherwise, so an occurrence that only takes
   content handed forward by a ranged override under amendment A3 is `false`.
   `solar_minutes` is the solar minute of `start_utc` for `office`
   (office-register.md), and `solar_in_window` is `true` when that minute lies
   in the solar window of the office row in force for the local start date.
   Rows are the schedule before settling, ordered by start instant and then by
   occurrence identifier.
5. `alias_resolutions.tsv`: columns `occurrence_id`, `ref`, `resolved` (empty
   when unresolved), `hops`, `outcome`; one row per occurrence and per distinct
   required attendee reference that the occurrence shows, amendment A3
   included, ordered by occurrence identifier and then by reference.
6. `resolutions.tsv`: columns `occurrence_id`, `tzid`, `nominal_local`,
   `classification`, `shift_minutes`, `utc_offset_minutes`; one row per
   expansion candidate that survives the `UNTIL` bound and the store window,
   including candidates an exclusion later removes and candidates an override
   later replaces, ordered by occurrence identifier and then by nominal wall
   clock value. `tzid` is the zone that resolved the candidate: the zone named
   by the `TZID` of the master `DTSTART` for a rule candidate, and the zone named
   by the `TZID` of its own property for an RDATE candidate. `nominal_local` is
   the candidate wall clock value, `classification` and `shift_minutes` are
   what zone-rules.md records for it, and `utc_offset_minutes` is the offset in
   force in that zone at the resolved instant. An RDATE value written as an
   absolute UTC instant names the zone of the master `DTSTART`, records as
   `nominal_local` the wall clock value of that instant in that zone, and is
   `unique` with a shift of zero.
7. `exceptions.jsonl`: every exclusion and override record, grouped by `kind`
   in the order `exdate-applied`, `exdate-unmatched`, `override-applied`,
   `override-rejected`, `shift`. An exclusion record has `collection`, `uid`,
   `exdate_utc`; an applied override has `collection`, `uid`,
   `recurrence_id_utc`, `range` (upper case, empty when absent) and
   `delta_minutes`; a rejected override has `collection`, `uid`,
   `recurrence_id_utc` and `reason` (`orphan-recurrence-id`,
   `superseded-recurrence-id` or `missing-master`); a shift record has
   `occurrence_id` and `applied_shift_minutes` and exists for every occurrence
   whose inherited shift in seconds is not zero. Within a kind, exclusion
   records are ordered by collection, UID and `exdate_utc`, override records by
   collection, UID, `recurrence_id_utc` and then `reason`, and shift records by
   occurrence identifier. Every record also carries its `kind`.
8. `zone_transitions.tsv`: columns `tzid`, `observance_count` (the number of
   `STANDARD` and `DAYLIGHT` subcomponents the zone declares), `onset_utc`,
   `from_offset_minutes`, `to_offset_minutes`; one row per merged transition
   whose onset is earlier than the end of the store window, however early the
   onset is, so a zone contributes its whole merged history up to the window
   end (the authority audit still compares only the onsets inside the window),
   zones ordered by `TZID`, transitions in transition list order.
9. `conflicts.jsonl`: one object per conflicting pair before settling, ordered
   by `first` and then `second`, with `first`, `second`, `shared_attendees`,
   `offices` (the two offices in pair order), `buffer_applied` (the buffer
   minutes added to the end of the earlier occurrence, an integer, `0` when the
   buffer does not apply) and `overlap_minutes`.
10. `settle_moves.csv`: columns `round`, `occurrence_id`, `from_utc`, `to_utc`
    (the start before and after the move), `deferred_minutes`,
    `gap_shift_minutes`, `reason_first`, `reason_second` (the `first` and
    `second` of the pair that caused the move), one row per deferral in the
    order the deferrals happen.
11. `settled_schedule.csv`: columns `occurrence_id`, `office`, `start_utc`,
    `end_utc`, one row per occurrence after settling, ordered by occurrence
    identifier.
12. `settle_summary.json`: `rounds`, `converged`, `stop_reason` (`clear`, `cap`
    or `pinned`), `buffer_minutes`, `quantum_minutes`, `round_cap`, `pin_rank`,
    `default_rank`, `effective_revision`, and `residual_conflicts`, pair objects
    as in `conflicts.jsonl` computed over the final schedule, empty when the
    pass converged.
13. `load_steps.tsv`: columns `attendee`, `step` (counting from 1),
    `occurrence_id`, `effective_office`, `deviation_minutes`, `cost_units`,
    `rest_days`, `decay_applied`, `office_changed`, `debt_after`; attendees
    ordered by identifier, steps in walk order.
14. `load_summary.json`: `floor`, `decay_per_rest_day`, `unit_minutes`, `cap`,
    `attendees` (an object keyed by attendee, each with `peak_debt` and
    `final_debt`, for every attendee required by at least one occurrence) and
    `over_cap` (objects with `attendee`, `peak_debt` and `excess`, ordered by
    attendee).
15. `attendance.psv`: columns `attendee`, `occurrence_id`, `effective_office`,
    `kind`, `local_start` (in the zone of the effective office),
    `minutes_outside`; one row per violation, ordered by attendee, then
    occurrence identifier, then kind.
16. `legs.json`: `legs`, one object per confirmed leg, ordered by departure
    instant and then leg id, each with `leg_id`, `attendee`, `depart_office`,
    `arrive_office`, `depart_utc`, `arrive_utc`, `depart_classification` and
    `arrive_classification` (what zone-rules.md classifies the two wall clock
    values as), `depart_shift_minutes` and `arrive_shift_minutes` (the shifts
    those two resolutions record), `duration_minutes` (the arrival instant
    minus the departure instant), `local_date_shift_days`,
    `utc_date_shift_days` (both arrival minus departure), `date_line_crossing`,
    and `blocked_from_utc` and `blocked_to_utc` (the two ends of the blocked
    window);
    and `counts` with `legs`, `date_line_crossings`, `blocked_occurrences` and
    `freebusy_conflicts` (the row counts of the two reports that follow).
17. `travel_blocks.csv`: columns `occurrence_id`, `attendee`, `leg_id`, `kind`,
    ordered by occurrence identifier and then leg id.
18. `busy_conflicts.tsv`: columns `occurrence_id`, `attendee`,
    `block_start_utc`, `block_end_utc`, `fbtype` (of the coalesced period),
    ordered by occurrence identifier, then block start, then attendee.
19. `sync_entries.tsv`: columns `collection`, `href`, `etag`, `revision`,
    `changed_local`, `changed_server`; collections in index order, hrefs sorted.
20. `sync_tokens.json`: `collections`, in index order, each with `collection`,
    `href` (the collection `href` of the index), `sync_token` and `resources`
    (its number of entries), and `counts`
    with `collections`, `resources` and `changed_resources` (resources whose
    merged projection differs from at least one replica).
21. `chargeback_offices.json`: `offices`, keyed by office code, each with
    `lines`, `base_cents`, `converted_cents` and `fx_bps`, for every office with
    at least one line; and `totals` with `lines`, `base_cents` and
    `converted_cents` over all offices.
22. `chargeback_collections.json`: `allocations`, keyed by collection and then
    by office, holding the allocated cents, for every collection and office
    that share at least one line; and `totals`, keyed by collection, holding
    the sum of its allocations.
23. `authority_audit.csv`: columns `subject`, `key`, `in_force`, `source`,
    `lower_value`, `agrees`.
24. `drift.csv`: columns `collection`, `uid`, `v3_count`, `v5_count`, `delta`.
25. `manifest.json`: `algorithm` (the string `sha256-chain`), `order` (the file
    names of reports 1 to 24 in this order), `links` (one object per report in
    that order, with `name`, `file_sha256` and `chain_sha256`), `chain_root` and
    `chain_head`.
