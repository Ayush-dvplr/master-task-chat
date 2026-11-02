STAGE Y01  Canonical event set
shift KP-2042-S23

This stage turns the move order journal into the canonical event
set of the shift. Nothing is decided about a move here beyond
which slot it belongs to and whether it exists at all.

RULE Y01.1  Withdrawal.
An order named in the withdrawn order journal with state
withdrawn and this shift's identifier is absent from the
canonical event set. It is not set aside by a rung of the
admission ladder, it is not published in the rejection journal,
and it takes no part in any later stage. A withdrawal row
carrying any other shift identifier is earlier material and
withdraws nothing here.

RULE Y01.2  The slot a minute belongs to.
Every order carries the minute it was raised and no slot. The
slot is derived from the minute using the boundary convention in
boundary_conventions.yaml. A minute that falls exactly on the
boundary between two slots belongs to the slot that is closing.
Minute zero belongs to the first slot.

RULE Y01.3  Beyond the last slot.
A minute strictly greater than the close of the last slot belongs
to no slot. The order is still a canonical event, its published
slot_code is the not supplied marker, and the admission ladder
settles it at the rung that catches a stale slot.

RULE Y01.4  Clusters are given.
The cluster tag on an order is read from the journal. This stage
forms no clusters of its own and picks no canonical member; the
pick happens at the admission stage, because it depends on which
members survive the earlier rungs.

PUBLISHES  canonical_events.csv
