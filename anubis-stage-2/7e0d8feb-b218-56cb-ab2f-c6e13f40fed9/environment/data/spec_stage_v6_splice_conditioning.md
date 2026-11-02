# V6 splice conditioning

Inputs: `break_plan_register.csv`, `gop_index_channel.psv`, and the snap
tolerance published in the settled sheet of `contract_terms_workbook.xlsx`.

## The nominal position

Each break carries a `nominal_offset_seconds` measured from the start of the
slot's material. It converts into whole channel frames by the carry rule
inside the scope `V6:` and the slot id, with the breaks of a slot converted
in ascending `break_no`.

## The index

`gop_index_channel.psv` publishes the channel frames at which the encoder
placed an index picture for a `content_ref`. A break can only be taken at an
index frame.

## R14 the snap

Let `t` be the position a break is aiming at and `T` the snap tolerance in
channel frames.

  If an index frame less than or equal to `t` exists and the greatest such
  frame is no more than `T` frames below `t`, the break snaps back to it.

  Otherwise, if an index frame greater than `t` exists, the break snaps
  forward to the least such frame.

  Otherwise, if an index frame less than or equal to `t` exists, the break
  snaps back to the greatest such frame whatever the distance.

  Otherwise the content has no index at all and the break stays where it is.

The published snap side is `SNAP_EXACT` when the snapped position equals
`t`, `SNAP_BACK` when it is below, `SNAP_FORWARD` when it is above, and
`SNAP_NONE` when the content carries no index frame.

## R15 the absorbed displacement

The displacement of a break is its snapped position less its nominal
position. Snapping moves breaks and the slot's material duration does not
change, so the displacement has to be absorbed inside the slot.

The last break of a slot aims not at its own nominal position but at its
nominal position less the sum of the displacements of every earlier break in
the same slot, floored at zero. It then snaps by R14 from that adjusted
target. Its published displacement is still measured against its own
nominal position.

A slot with one break has nothing to absorb and its single break aims at its
own nominal position. Snapping every break in a slot independently is
locally defensible and is wrong.

## Published

`break_positions.csv` publishes the nominal frame, the adjusted target
frame, the position frame, the snap side, the displacement and the carry
held after that break's conversion, ordered by slot and then by break
number.
