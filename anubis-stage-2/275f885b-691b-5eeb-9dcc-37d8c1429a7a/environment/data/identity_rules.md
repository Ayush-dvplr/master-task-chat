# Identity rules

## Holding keys

A requisition carries a holding key as the field office typed it. The key is normalised before
any join: trim surrounding space, upper case the text, drop everything from the first forward
slash onward, keep the digits, and write the result as `BLK-` followed by those digits padded
with leading zeroes to four places. A key with no digits resolves to nothing.

## Alias hops

`block_alias_map.csv` maps a normalised key to the key that replaced it. A mapping applies when
the start of the round window falls at or after `effective_from` and strictly before
`effective_to`, and an empty `effective_to` leaves the mapping open. Where two mappings for one
key apply on the same date, the one with the later `effective_from` applies, and `issued_at`
breaks a remaining tie. Resolution follows mappings until it reaches a key that appears in
`block_master.csv`, and it may take at most the number of hops declared as `alias.max_hops`.
A key that still has no master record after that many hops resolves to nothing, and so does a
key whose mappings return to a key already visited.

## Master versions

`block_master.csv` holds one row per version of a block. The version in force for a round is
the one with the latest `valid_from` at or before the start of the round window, with
`record_id` breaking a tie. Region, segment, species and age class come from that version. The
species and age class a requisition states are recorded for the audit and decide nothing.

A block is withdrawn for a round when the version in force carries a `withdrawn_from` date at
or before the start of the round window.

## Restock epochs

A `restock` event in the visit stream opens a new epoch for the block. The epoch in force for a
round is one plus the number of `restock` events for that block that occurred strictly before
the start of the round window, measured in universal time. The identity of a claim is the block
reference, the character `#`, and the epoch in force.

Running quantities belong to an identity. An identity that appears for the first time starts
every running quantity at zero.

## Collapse of repeated rows

Requisition rows that resolve to the same identity and settle in the same round form one group.
The earliest `recorded_at` in the group opens a span of the length declared as
`collapse.window.hours`. The surviving row is the latest row recorded inside that span, with
`req_ref` breaking a tie. Other rows inside the span are counted as collapsed duplicates. Rows
recorded after the span closes are counted as stale revisions and decide nothing.
