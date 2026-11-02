STAGE Y05  Canonical event order
shift KP-2042-S23

This stage puts the canonical events in the one order every later
stage walks them in.

RULE Y05.1  The source rank.
source_priority_register.csv gives every source system a priority
rank. Read it through revision_precedence.toml: rows of another
shift and rows marked retired are set aside, and the surviving
row with the highest revision_seq is applicable. A lower rank
number outranks a higher one. The rank order is not the order the
sources appear in any paper and it is not their alphabetical
order.

RULE Y05.2  The order.
Events ascend by slot ordinal, then by source priority rank, then
by event_seq, then by box_id, then by order_id. An event with no
slot sorts after every event that has one. The last key settles
every remaining tie by itself, so the order is total and does not
depend on the order the journal happens to list.

RULE Y05.3  The event key.
The event key is the position of the event in that order,
counting from one. Every later stage names events by this key.

PUBLISHES  event_order.csv
