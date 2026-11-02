# V8 drift correction

Inputs: the placement from V7, `filler_library.csv`, and the flexible part
named by each slot in `transmission_schedule.csv`.

## R18 an overrun

When the running cursor at a fixed junction is later than the junction's
scheduled offset, the day is overrunning by the difference.

The overrun is removed by trimming flexible parts, starting with the slot
immediately before the junction and walking backwards. The walk stops at the
previous fixed junction, and it includes that junction's own slot, because a
fixed junction pins a start and not an end.

A slot can give up at most the whole of its flexible part and never more, so
the floor of every trim is zero frames of flexible part remaining. The trim
taken from the slot immediately before the junction is recorded with the
reason `CR_TRIM_FLEX`, and every trim taken from a slot further back is
recorded with the reason `CR_TRIM_BACKFILL`.

If the overrun still cannot be removed after the whole walk, the residue is
recorded with the reason `CR_TRIM_SHORTFALL` and the junction is pinned
anyway. The slots between the previous fixed junction and this one are then
re-placed from the previous junction's start with their trimmed durations.

## R19 an underrun

When the running cursor at a fixed junction is earlier than the junction's
scheduled offset, the gap is filled.

The filler is chosen from `filler_library.csv` by walking the rows in
ascending `predicate_order` and taking the first row for which all three of
these hold:

  the row's `stock_state` is `FS_AVAILABLE`
  the row's `daypart_ref` is the junction slot's daypart or is `DP_ANY`
  the gap in frames is at least `min_frames` and at most `max_frames`

The first such row wins. If no row qualifies, the house filler named by
`house_filler_ref` in `channel_config.json` is used and the published
selection index is `0`. The fill is recorded with the reason
`CR_FILL_INSERT` and the filler is taken to occupy exactly the gap.

## R20 a junction that needs nothing

A fixed junction the cursor reaches exactly is recorded with the reason
`CR_NO_CHANGE` and a frame count of zero.

## Published

`slot_placement.csv` publishes every slot. `conform_trace.json` publishes
the corrections in the order they were made, numbered from one, with the
totals by reason and the day end frame. `filler_plan.csv` publishes the
fills.
