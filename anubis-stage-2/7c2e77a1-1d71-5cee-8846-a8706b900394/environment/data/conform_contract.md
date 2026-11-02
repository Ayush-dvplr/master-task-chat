# Conform contract

Tier: contract.

This document governs how a delivery timeline is rebuilt from source clip events. It is the single source of truth for the conform run. Where any other file in this folder disagrees with it, this document holds.

A conform run is named by a scenario. The five live scenarios are `visible`, `peak`, `steady`, `burst` and `latency`. The name `archive` occurs in several reference tables and names no live scenario.

## 1. Scenario settings

Two settings govern a scenario: `delivery_family` and `tape_cutover_utc`.

Settings live in `conform.ini` and `site_overrides.ini`. Each file holds named sections. The section of a scenario is `scenario.` followed by the scenario name. One setting for one scenario resolves by consulting, in order, the scenario section of `site_overrides.ini`, then the scenario section of `conform.ini`, then the section named by the `inherits` key of the scenario section, with the same two file order applied at that section, and so on. The first consulted section that carries the setting supplies its value. When the `inherits` key of a section is present in both files, the value in `site_overrides.ini` supplies the next section. A chain that arrives at a section already consulted yields the reason code `CFG_CYCLE` for every event of the scenario.

The cutoff instant of a scenario is `scenarios.<name>.cutoff_utc` in `scenario_cutoffs.json`.

The excluded classes of a scenario come from `scenarios.<name>.exclude_classes` in the same file. When that key holds a list, including an empty list, the list is the excluded set. When the key is absent, and when its value is null, the excluded set is `defaults.exclude_classes`.

House wide settings live in `house.properties`.

## 2. Event records

Event rows arrive in the shard files named in `index.md`. A scenario reads every shard whose name carries that scenario name. Rows are identified by field position, not by title. Field ten is the speed of the event in parts per million and is the value this contract uses. Field nineteen is a percentage reading of the same measurement kept for display. `format_notes.md` records the field order and the written forms.

The recorded time of an event resolves as follows. The ingest logs named in `index.md` carry `INGEST` lines, some of which name an event uid. When at least one such line names a uid, the recorded time of that event is the timestamp of the last such line in the reading order of the ingest logs, converted to UTC with `host_clock_offsets.csv` using the row for the line host whose window contains that timestamp. When no such line names a uid, field fifteen of the event row is the recorded time. `provenance_spec.md` records the reading order of the ingest logs and the sense of the conversion.

An event is admitted to a scenario when its resolved recorded time is at or before the scenario cutoff instant. An event whose resolved recorded time falls after the cutoff instant takes no part in the run and appears in no artifact.

## 3. Corrections

The correction streams named in `index.md` carry amendments to event rows. Each record names an event uid, a revision, an operation of `amend` or `delete`, a field map, a recorded time and a source system.

Only correction records whose recorded time is at or before the scenario cutoff instant take part. Among those, only records whose revision is strictly greater than field twenty one of the event row take part.

Of the records that take part for one uid, exactly one applies: the record carrying the highest revision. Records at lower revisions are superseded and contribute nothing, whatever their operation. When the applying record is an `amend`, its field map replaces the named fields of the event row. When the applying record is a `delete`, the event is withdrawn and carries the reason code `WITHDRAWN`.

Two records for one uid that carry the same revision, the same source system, the same operation and the same field map are one record counted once.

Two records for one uid that carry the same highest revision and differ otherwise are a tie. A tie settles under the ordering that `arbitration_notes.log` records for historical ties of the same shape, read together with `source_tiers.csv`. A tie that the recorded ordering leaves undecided yields the reason code `TIE_UNRESOLVED`.

The field names the correction streams use for event fields are listed in `format_notes.md`.

## 4. Overrides

The override streams named in `index.md` carry single field instructions issued by named approvers. Overrides apply to the event row after corrections have applied.

An override takes part when its recorded time is at or before the scenario cutoff instant. An override applies to its event when both of the following hold: its recorded time is strictly after the resolved recorded time of the event, and `authority_roles.csv` carries a row whose approver is the override approver, whose `field_scope` is the override field or the word `all`, and whose window contains the override recorded time. An override that takes part and does not apply contributes nothing.

When two or more overrides apply to the same field of the same event, the one with the latest recorded time applies. When that leaves two, the one with the greater approver string applies, as `override.tie.breaker` in `house.properties` records.

## 5. Identity

The asset reference of an event row is written in vendor form. Its vendor key is the reference with spaces and hyphens removed, upper cased, with the leading run of letters kept, the digit run left padded with zeros to the width `alias.key.pad.width` in `house.properties`, and the trailing letters kept. The reference `vn 1-a` has vendor key `VN000001A`.

`alias_hops_vendor.tsv` carries one house code per vendor key per window. The window that contains the event effective time supplies the house code. A vendor key with no window containing the event effective time yields `ALIAS_UNKNOWN`.

`alias_hops_house.tsv` carries one target code per house code per window. A house code resolves by following targets, each step using the window that contains the event effective time, until a target is reached that `alias_hops_house.tsv` does not carry as a house code. That target is the canonical code. A chain that returns to a code already visited yields `ALIAS_CYCLE`. A chain longer than `alias.max.hops` in `house.properties` yields `ALIAS_CYCLE`.

The identity of an event is the pair of its canonical code and field five of the event row. The asset tables named in `index.md` carry one row per such pair and supply the asset family code. A pair that no asset table carries yields `ASSET_UNKNOWN`.

## 6. Source measurement

`rate_families.csv` carries one rate family per family code per window. The window that contains the event effective time supplies the rate family, the frame rate numerator, the frame rate denominator, the nominal frame rate and the drop frame flag. A family code with no window containing the event effective time yields `RATE_UNKNOWN`.

Timecodes convert to frame counts under `timecode_spec.md`, using the nominal frame rate and the drop frame flag of the rate family.

The in timecode, the out timecode and the speed of an event come from the event row, except where `provenance_spec.md` directs otherwise.

The source span of an event is the out frame count plus field seventeen of the event row, less the in frame count. A source span at or below zero yields `SPAN_NONPOSITIVE`.

`handle_policy.tsv` carries one handling value per event class per site code per window. The window that contains the event effective time supplies the handling. A handling of `excluded` sets the net source frames to the source span less field eight and less field nine of the event row. A handling of `retained` sets the net source frames to the source span. Net source frames at or below zero yield `HANDLE_OVERRUN`.

The speed of an event is read in parts per million, where one million is unity. A speed at or below zero yields `RATE_INVALID`. The net adjusted source frames of an event is the net source frames multiplied by one million and divided by the speed, rounded to a whole frame under the mode `rounding.mode` in `house.properties`. The stage named by `rounding.stage` in `house.properties` is the only stage of the conform at which a quantity is rounded; every other quantity in this contract is a whole number already.

## 7. Cadence

The delivery family of the run is the `delivery_family` setting of the scenario. The source family of an event is the rate family of its asset family code.

`cadence_map.tsv` carries a numerator and a denominator for each triple of site code, source family and delivery family. The site code of an event is field twenty two of the event row, as corrections and overrides may have left it. A triple that `cadence_map.tsv` does not carry yields `CADENCE_UNKNOWN`.

Every timeline carries a cadence phase. The phase of a timeline is zero before its first event. Writing `p` for the phase of the timeline as the event is reached, `n` for the net adjusted source frames of the event, and `num` and `den` for the cadence of the event, the record span of the event is the whole number part of `(p + n)` times `num` divided by `den`, less the whole number part of `p` times `num` divided by `den`. The phase after the event is the remainder of `p + n` on division by `den`.

The phase carries from one applied event of a timeline to the next applied event of the same timeline. An event that is audited or rejected leaves the phase of its timeline unchanged. The policy `phase.reset.policy` in `house.properties` records the only circumstance under which a phase returns to zero inside a timeline.

## 8. State

`transition_matrix.csv` carries a legality of `apply` or `audit` for each triple of event class, state from and state to. The three values of an event come from fields eleven, twelve and thirteen of the event row, as corrections and overrides may have left them. A triple that `transition_matrix.csv` does not carry yields `TRANSITION_UNKNOWN`. A triple whose legality is `audit` yields `ILLEGAL_TRANSITION`.

A timeline whose latest applied event carried a state to of `withdrawn` is closed. Every later event of a closed timeline yields `TERMINAL_STATE`, except an event whose class is `reinstate`, which resolves as any other event and reopens the timeline when it applies.

## 9. Nesting

An event whose class is `nest` draws its net source frames from another timeline rather than from its own timecodes. `nesting_edges.tsv` carries the required timeline of such an event under the scenario of the run, and is the only statement of that relation. An event of class `nest` for which the file carries no row under the scenario of the run yields `NEST_MISSING`.

The net source frames of a nest event is the record frames of its required timeline. Handling for a nest event is `retained`. The speed stage and the cadence stage of a nest event apply as for any other event.

Timelines resolve in an order in which every timeline required by a nest event resolves before the timeline holding that event, with timelines that are free to resolve taken in ascending timeline identifier. A set of timelines that require one another in a closed ring, and every timeline that requires a member of such a ring directly or through further nest events, resolve with record frames of zero, with exit phase of zero, and with every one of their events yielding `NEST_CYCLE`.

The depth of nesting a run accepts is `nest.max.depth` in `house.properties`.

## 10. Timeline walk

The events of a timeline resolve in ascending event effective time, then ascending field three of the event row, then ascending event uid.

A timeline carries a record cursor that is zero before its first event. An applied event takes its record in frame count from the cursor and its record out frame count from the cursor plus its record span, and then advances the cursor to its record out frame count. An audited or rejected event leaves the cursor where it is and takes both its record in frame count and its record out frame count from the cursor.

The record frames of a timeline is its cursor after its last event. The exit phase of a timeline is its phase after its last event.

## 11. Delivery exceptions

`delivery_exceptions.csv` carries exceptions per scenario and timeline. Each row names an action, an effective time, a recurrence, an until instant, a weekday and a time of day.

A row whose recurrence is `none` has one occurrence, at its effective time. A row whose recurrence is `weekly` has one occurrence on each named weekday at the named time of day, from the first such instant at or after its effective time through its until instant inclusive.

An action of `suppress` yields `DELIVERY_SUPPRESSED` for every event of the named timeline whose effective time falls at or after an occurrence and before that occurrence advanced by `suppress.window.hours` in `house.properties`.

An action of `clear_phase` returns the phase of the named timeline to zero at each of its occurrences. The return takes effect before the first event of the timeline whose effective time is at or after the occurrence, and the cursor of the timeline is untouched.

## 12. Reason codes

`reason_codes.json` carries the closed set of reason codes with a kind and a remedy for each. A code of kind `reject` makes its event rejected. A code of kind `audit` makes its event audited. An event that draws no code is applied and carries `OK`.

When more than one code is available for an event, the earliest code in this order is the code of the event: `WITHDRAWN`, `TIE_UNRESOLVED`, `ALIAS_UNKNOWN`, `ALIAS_CYCLE`, `ASSET_UNKNOWN`, `RATE_UNKNOWN`, `TRANSITION_UNKNOWN`, `NEST_MISSING`, `NEST_CYCLE`, `SPAN_NONPOSITIVE`, `HANDLE_OVERRUN`, `RATE_INVALID`, `CADENCE_UNKNOWN`, `CFG_CYCLE`, `DELIVERY_SUPPRESSED`, `TERMINAL_STATE`, `CLASS_EXCLUDED`, `ILLEGAL_TRANSITION`.

A code is available to an event only where the event reaches the point that settles it. State and delivery are settled first, so `DELIVERY_SUPPRESSED`, `TERMINAL_STATE`, `CLASS_EXCLUDED` and `ILLEGAL_TRANSITION` are available to every admitted event that clears sections 3 to 5 and section 9. An event drawing one of those four is not measured, so `SPAN_NONPOSITIVE`, `HANDLE_OVERRUN`, `RATE_INVALID` and `CADENCE_UNKNOWN` are available only to an event that reaches the measurement of section 6 and the cadence of section 7. The order above settles a contest among the codes an event actually drew. A timeline that section 9 settles as a ring stands apart from that contest: every event of such a timeline takes `NEST_CYCLE` whatever else it drew.

An event whose class is in the excluded set of the scenario yields `CLASS_EXCLUDED`.

## 13. Scenario record fields

A scenario result carries the scenario name, the cutoff instant as written in `scenario_cutoffs.json`, the resolved delivery family, a timeline list and a totals map.

A timeline entry carries the timeline identifier, its record frames, its exit phase, the count of its applied events, the count of its audited events, the count of its rejected events, and its event list in resolution order.

An event entry carries the event uid, the canonical code, the generation, an outcome of `applied`, `audited` or `rejected`, the reason code, the net adjusted source frames of the event, the record in frame count, the record out frame count, the phase as the event was reached and the phase after the event. An event that is audited or rejected carries net adjusted source frames of zero and carries the phase of its timeline unchanged in both phase fields. An event whose canonical code did not resolve carries the empty string for the canonical code.

The totals map carries the count of timelines, the count of events, the count of applied events, the count of audited events, the count of rejected events, the sum of record frames over timelines and the sum of exit phases over timelines.

## 14. Tallies

A tally of reason codes covers the codes whose kind in `reason_codes.json` is `reject` or `audit`. The code `OK` takes no part in any tally, in any ranking and in any map of counts. A code that occurs nowhere in the run is left out of every map rather than carried at zero. A ranking of codes reads by falling count and then by rising code.

A tally of stage visits ranks by falling visit count and then by rising stage name.

A nest event whose row in `nesting_edges.tsv` names a timeline the scenario does not carry takes net source frames of zero, which section 6 then settles as `HANDLE_OVERRUN`.

A nesting chain running deeper than `nest.max.depth` stands as a closed ring and section 9 settles it as `NEST_CYCLE`.

Where no row of `handle_policy.tsv` covers the pair of event class and site code at the effective instant, handling is `retained`.
