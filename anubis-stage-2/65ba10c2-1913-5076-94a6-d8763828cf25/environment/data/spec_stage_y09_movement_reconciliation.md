STAGE Y09  Planned against physical
shift KP-2042-S23

This stage sets the planned stream against the physical stream.
The two are separate sources of evidence about one movement and
neither is a copy of the other.

RULE Y09.1  Which confirmation belongs to an order.
A confirmation belongs to an order when it names that order. When
more than one confirmation names one order the one with the
lowest confirmed minute is the one that counts. A confirmation
may carry a minute earlier than the minute its order was raised;
that is ordinary and changes nothing about which confirmation
counts.

RULE Y09.2  The movement state.
An admitted order with a landed confirmation is confirmed. An
admitted order with a confirmation in any other state is aborted.
An admitted order with no confirmation is unconfirmed. An order
the ladder set aside is contradicted when a landed confirmation
names it, and set_aside otherwise.

RULE Y09.3  A confirmation does not overturn the ladder.
A contradicted order stays set aside. Its box does not move, no
capacity is taken and no reservation is consumed. The
contradiction is recorded and nothing else about the shift
changes because of it. Treating a landed confirmation as evidence
that the move happened, and moving the box, is wrong.

RULE Y09.4  A confirmation with no order.
A confirmation whose order_id is empty belongs to no order. It is
counted as a loose confirmation, in ascending confirm_id, and it
moves nothing.

PUBLISHES  movement_accounting.jsonl
