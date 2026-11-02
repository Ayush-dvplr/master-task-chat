# V7 schedule placement

Inputs: `transmission_schedule.csv`, and the material durations from V5.

## R16 the broadcast day

Each slot carries a `sched_start_tc` as a channel drop frame timecode,
counted under the channel's drop frame behaviour whatever separator it was
keyed with (R40). Its scheduled offset is the frame count of that label less the frame count of
the day start label `06:00:00;00`. A label whose frame count is less than
the day start belongs to the following calendar day, and one whole broadcast
day of `2589408` frames is added to the difference.

Slots run in ascending scheduled offset, ties broken by ascending `slot_id`.
The sequence number published for a slot is its one based position in that
order.

## R17 a slot with no canonical asset

A slot whose `content_ref` has no canonical attempt is dropped from the day.
It is published in `slot_placement.csv` with a `sequence_no` of `0`, a
`placement_state` of `PL_DROPPED`, every frame column at zero and an empty
hour label, and a correction with the reason `CR_SLOT_DROPPED` is recorded
against it. It occupies no time and the slots after it move up.

## The junctions

A slot whose `junction_kind` is `JK_FIXED` publishes a junction that cannot
move: its placed start is its scheduled offset, always. A slot whose
`junction_kind` is `JK_FLOAT` starts where the slot before it ended.

The first slot of the day is a fixed junction.

## The running placement

Placement runs forward through the ordered slots. A floating slot starts at
the running cursor. A fixed slot starts at its scheduled offset, and the
difference between the running cursor and that offset is the correction V8
has to make. After a slot is placed the cursor moves to the slot's start
plus its transmitted frames, which are its material frames less any frames
V8 trimmed from it.
