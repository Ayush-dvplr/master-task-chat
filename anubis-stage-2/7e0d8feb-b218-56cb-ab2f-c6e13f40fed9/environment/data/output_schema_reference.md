# Output schema reference

Column orders are exactly as published here. Delimited artifacts carry a
header row.

## `asset_register.csv`

`content_ref, canonical_ingest_id, revision_no, qc_state, rate_code,
rate_num, rate_den, tc_base, drop_frame, som_tc, eom_tc, source_frames,
channel_frames_exact, house_no, anchor_ingest_id, inclusion_state`

One row per cluster, ordered by `content_ref`. `drop_frame` is `yes` or
`no`. `channel_frames_exact` is a ratio to ten decimal places.
`som_tc` and `eom_tc` are the canonical attempt's labels exactly as the
ingest register records them, separator included.
`inclusion_state` is `AS_INCLUDED` or `AS_EXCLUDED`. An excluded row leaves
every field from `canonical_ingest_id` through `channel_frames_exact` empty
except `house_no` and `anchor_ingest_id`, which are always published.

## `segment_conform.csv`

`slot_id, content_ref, part_no, part_kind, retention_state, source_frames,
channel_frames_exact, channel_frames, carry_after`

One row per part of each placed slot, ordered by `slot_id` and then by
ascending `part_no`. `retention_state` is `PR_RETAINED`, `PR_TRIMMED_HEAD`
or `PR_TRIMMED_TAIL`. A trimmed part publishes `channel_frames` of `0` and
the unchanged `carry_after` of its scope.

## `break_positions.csv`

`slot_id, break_no, break_ref, nominal_offset_seconds, nominal_frame,
adjusted_target_frame, position_frame, snap_side, displacement_frames,
avail_seconds, carry_after`

One row per break of each placed slot, ordered by `slot_id` and then by
ascending `break_no`.

## `slot_placement.csv`

`slot_id, content_ref, sequence_no, junction_kind, sched_start_frame,
actual_start_frame, material_frames, trim_frames, transmitted_frames,
end_frame, drift_frames, hour_label, daypart_ref, placement_state`

One row per slot in the schedule, ordered by ascending `sequence_no` and
then by `slot_id`, so dropped slots with a sequence number of zero come
first.

`placement_state` is `PL_PLACED` for a placed slot and `PL_DROPPED` for a
dropped one, and the slot's element in `reconciliation.xml` carries the
same token. `drift_frames` is `actual_start_frame` less `sched_start_frame`.
`hour_label` is the clock hour that holds `actual_start_frame`, and is empty
for a dropped slot.

## `conform_trace.json`

An object with `corrections`, `totals`, `day_end_frame` and
`correction_count`. Each correction carries `sequence`, `slot_id`,
`reason`, `frames`, `detail_slot` and `filler_ref`. `totals` maps each
reason that occurred to its count. `day_end_frame` is the greatest
`end_frame` in `slot_placement.csv`, and `playout_schedule.ini`,
`day_report.md` and `manifest.json` publish the same value.

`slot_id` is the fixed junction the correction was made at, or the dropped
slot for `CR_SLOT_DROPPED`. `detail_slot` is the slot whose flexible part
gave up the frames for `CR_TRIM_FLEX` and `CR_TRIM_BACKFILL`, and is the
same slot as `slot_id` for every other reason. `filler_ref` is the chosen
filler for `CR_FILL_INSERT` and the empty string for every other reason.
The corrections of the placement walk come first, in the order the walk
made them, and the `CR_SLOT_DROPPED` corrections follow them in ascending
scheduled offset, ties by `slot_id`.

## `filler_plan.csv`

`slot_id, junction_offset_frame, gap_frames, filler_ref, daypart_ref,
selection_index`

One row per fill, ordered by `slot_id`.

## `avail_plan.tsv`

`market_ref, break_ref, break_position_frame, position_in_break, order_ref,
advertiser_ref, separation_class, spot_frames, start_frame, end_frame,
hour_label`

`hour_label` is the clock hour that holds the spot's `start_frame`. It
labels the spot; the advertising frames of each clock hour are counted as
`spec_stage_v13_minutage_compliance.md` sets out.

## `deferral_ledger.jsonl`

One object per line with `order_ref`, `market_ref`, `break_ref`,
`deferral_reason`, `predicate_index` and `spot_frames`.

## `market_overrides.csv`

`market_ref, slot_id, content_ref, rule_id, precedence, substitute_ref,
override_flag, national_break_count, substitute_break_count`

## The four per market avail files

An object with `market_ref`, `break_count`, `capacity_frames_total`,
`carry_residual_capacity`, `carry_residual_substitute` and `breaks`. Each
break carries `break_ref`, `slot_id`, `break_no`, `origin`,
`position_frame`, `capacity_frames`, `daypart_ref` and `hour_label`.
`origin` is `BO_NATIONAL` or `BO_SUBSTITUTE`.

## `market_avail_stream.jsonl`

One object per line, the union of the four market break lists with
`market_ref` added, ordered by market reference, then position frame, then
break reference.

## `settlement_ledger.psv`

`order_ref, advertiser_ref, market_ref, break_ref, currency,
delivered_frames, unbilled_frames, billable_grains, rate_card_ref,
effective_from, minor_per_grain, gross_minor, commission_minor, net_minor,
gross_major`

`unbilled_frames` is the whole number of the spot's frames that R41 left
unbilled, and `0` for a spot that lost none.

## `makegood_ledger.json`

An object with `advertisers`, `allocated_total_minor`, `cap_num` and
`cap_den`. Each advertiser entry carries `advertiser_ref`,
`day_gross_minor`, `cap_minor`, `raw_total_minor`, `allocated_total_minor`
and `obligations`. Each obligation carries `order_ref`, `deferral_reason`,
`raw_minor` and `allocated_minor`. The `deferral_reason` of an obligation an
admitted spot raised under R41 is `DF_OVER_CAP`.

## `exception_ledger.jsonl`

One object per line with `order_ref`, `exception_code`, `rate_card_ref` and
`detail`. The `detail` text is fixed per code and carries no other wording.
An `EX_ZERO_DELIVERY` record carries the detail `admitted spot occupies no
channel frame`. An `EX_NO_CARD` record carries the detail `earliest card
dated ` followed by the earliest `effective_from` of the order's rate card
reference, and an empty date when the book carries no row for that
reference at all.

## `advertiser_summary.csv`

`advertiser_ref, currency, admitted_spots, deferred_spots, delivered_frames,
gross_minor, commission_minor, net_minor, makegood_minor, gross_major`

## `minutage_report.csv`

`market_ref, hour_label, daypart_ref, advertising_frames,
advertising_seconds, cap_frames, headroom_frames, breach_state`

`advertising_seconds` is a ratio to ten decimal places. `breach_state` is
`MB_WITHIN` or `MB_BREACH`.

## `carry_ledger.json`

An object with `scopes`, `scope_count`, `conversion_count` and
`residual_total`. Each scope carries `scope`, `conversions` and `residual`,
ordered by scope name ascending. `residual` and `residual_total` are ratios
to ten decimal places.

## `reconciliation.xml`

A `reconciliation` root element with the attributes `channel_ref` and
`transmission_date`, then one `slot` element per slot ordered by `slot_id`,
then one `totals` element. Two space indent, one attribute set per line, and
one trailing line feed.

The first line is the declaration `<?xml version="1.0" encoding="UTF-8"?>`.
Each `slot` element is empty and carries these attributes in this order:
`slot_id`, `placement_state`, `prior_start_frame`, `start_frame`,
`start_delta`, `prior_material_frames`, `material_frames`,
`material_delta`, `prior_break_count`, `break_count` and `break_delta`. The
`totals` element is empty and carries `slots`, `agreeing`, `differing`,
`absolute_start_delta` and `absolute_material_delta` in that order. A slot
the prior register does not carry reads as a prior start frame, a prior
material frame count and a prior break count of zero. Every element sits on
its own line, attribute values are double quoted, and an empty element
closes with `/>` written directly after its last attribute.

## `playout_schedule.ini`

A `[channel]` section carrying `channel_ref`, `transmission_date`,
`day_start_tc`, `day_end_frame` and `placed_slot_count`, then one
slot section per placed slot in placement order, headed by the word slot
and a colon and the slot id inside square brackets, carrying
`content_ref`, `sequence_no`, `start_frame`, `start_tc`,
`transmitted_frames`, `trim_frames` and `break_count`. Keys are written as
`key = value`. Sections are separated by one blank line and the file ends
with one line feed.
`start_tc` is the channel drop frame timecode label of the slot's placed
start: the day start label plus `start_frame`, taken into one timecode day
and written `hh:mm:ss;ff`. Each section carries its keys in the order
listed above.

## `day_report.md`

Markdown, in this exact shape, with one blank line under every heading and
one blank line before the next heading.

The level one heading is `# Transmission day report`. Then a bullet list,
one figure per line written as `- key: value`, carrying `channel_ref`,
`transmission_date`, `instance_ref`, `live_control_set`, `scheduled_slots`,
`placed_slots`, `dropped_slots`, `day_end_frame`, `corrections`,
`admitted_spots`, `deferred_spots`, `gross_minor_total` and
`makegood_minor_total`, in that order. `live_control_set` here is the
`workbook_control_set` field of the channel configuration. `corrections` is
the correction count of `conform_trace.json`, and `gross_minor_total` is the
sum of the `gross_minor` column of `settlement_ledger.psv`.

Then the level two heading `## Correction totals` and one bullet per
correction reason written as `- reason: count`, covering every reason in
`correction_reason_reference.txt` in ascending reason order whether or not
it occurred.

Then the level two heading `## Deferral totals` and one bullet per deferral
reason written as `- reason: count`, covering every reason in
`deferral_reason_reference.txt` in ascending reason order whether or not it
occurred. Each count is the number of deferrals in `deferral_ledger.jsonl`
with that reason, except `DF_OVER_CAP`, which is never a deferral: its count
is the number of obligations in `makegood_ledger.json` with that reason.

## `compliance_summary.md`

Markdown, in this exact shape, with one blank line under every heading and
one blank line before the next heading.

The level one heading is `# Compliance summary`. Then a bullet list, one
figure per line written as `- key: value`, carrying
`regulatory_minutes_per_clock_hour`, `cap_frames`,
`separation_minimum_positions`, `billing_grain_seconds`,
`snap_tolerance_frames` and `breach_hours`, in that order. `cap_frames` is
the standing cap, the one the Section 1 figure gives, whatever Section 2
sets for single market hours. `breach_hours` is the number of rows of
`minutage_report.csv` whose breach state is `MB_BREACH`.

Then the level two heading `## Advertising frames by market` and one bullet
per market written as `- market_ref: frames`, ordered by market reference
ascending, where the count is that market's advertising frames summed over
the twenty four clock hours.

Then the level two heading `## Breach hours` and one bullet per breaching
row of `minutage_report.csv` in that file's order, written as
`- market_ref hour_label frames N over C` with `N` the advertising frames
and `C` the cap frames of that row. A day with no breaching hour publishes the single
bullet `- none`.

## `manifest.json`

An object carrying `instance_ref`, `channel_ref`, `transmission_date`,
`artifact_count`, `core_order`, `digest`, `slot_count`,
`placed_slot_count`, `dropped_slot_count`, `admitted_spot_count`,
`deferred_spot_count`, `breach_hour_count`, `live_control_set`,
`snap_tolerance_frames`, `makegood_cap_num`, `makegood_cap_den`,
`separation_minimum_positions`, `billing_grain_seconds`,
`regulatory_minutes_per_clock_hour` and `day_end_frame`.
`live_control_set` is the name of the workbook sheet the control set
selected.
