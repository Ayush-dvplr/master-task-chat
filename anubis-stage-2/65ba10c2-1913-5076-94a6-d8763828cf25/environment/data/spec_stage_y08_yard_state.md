STAGE Y08  Yard state through the shift
shift KP-2042-S23

This stage carries the yard state forward through the shift.

RULE Y08.1  What an admitted order does.
An admitted order takes its box out of the cell it stood in, if
it stood in one, and puts it in the block, row and tier the order
names. The count of the block it left falls by one and the count
of the block it enters rises by one.

RULE Y08.2  The history.
One row is published per admitted order, in ascending event key,
carrying where the box came from and where it went. A box that
had no yard position carries the not supplied marker in the three
from columns and a was_stacked of no.

RULE Y08.3  The closing state.
The closing position of a box is where its last admitted order
put it, or its opening position when no order moved it, or no
position at all when it was off the yard and stayed there.

RULE Y08.4  The per slot occupancy.
The occupancy of a block at the close of a slot is the occupancy
after every admitted order of that slot and of every earlier slot
has been carried out, and before any order of a later slot. The
capacity stage reads these snapshots.

RULE Y08.5  Every block is published.
Every block in force appears in the published occupancy, an empty
one included, with its opening count, its closing count and its
closing free capacity.

PUBLISHES  yard_occupancy.psv, container_state_history.psv,
container_state_final.csv
