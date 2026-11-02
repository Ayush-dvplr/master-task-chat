# V5 segment assembly

Inputs: `segment_part_manifest.tsv`, the assets from V1 to V3, and the
placed slots from V7.

## The parts of a slot

A slot transmits the parts of its `content_ref` in ascending `part_no`.
Each part carries its own `part_som_tc` and `part_eom_tc` at the asset's
timecode base and drop frame flag, and its span is taken by the V3 rule.
Part labels are counted under R40 whatever separator they were keyed with.

## R12 black trimming

Parts whose `part_kind` is `PT_BLACK` are trimmed when they sit at the head
or at the tail of the part sequence. A run of black at the head is trimmed,
a run of black at the tail is trimmed, and black anywhere between two parts
that are not black is transmitted.

A trimmed part is published with the retention state `PR_TRIMMED_HEAD` or
`PR_TRIMMED_TAIL`, contributes nothing to the material duration, and makes
no conversion, so it consumes no carry.

## R13 an asset with no parts

An asset with no rows in the part manifest transmits as a single part
covering the whole V3 span, published with `part_no` of `0` and a
`part_kind` of `PT_PROGRAMME`.

## The material duration

The material duration of a slot is the sum of the whole channel frame counts
of its retained parts, each produced by the carry rule inside the scope
`V4:` and the slot id.

## The flexible part

The transmission schedule names one `flex_part_no` per slot. That part is
the slot's flexible element and V8 trims it when a fixed junction has to be
met. The flexible part is always a tail element of the slot, so trimming it
moves no break position inside the slot.

The flexible part is the transmitted part whose `part_no` equals the slot's
`flex_part_no`. When no part of the slot carries that number, as with an
asset transmitted whole under R13 as part `0`, the slot has no flexible part
and gives up nothing to a trim.
