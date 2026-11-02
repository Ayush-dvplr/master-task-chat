STAGE Y11  Block capacity state
shift KP-2042-S23

This stage publishes what each block held and what was withheld
from it, slot by slot.

RULE Y11.1  One row per block and slot.
Every block in force is published against every slot of the
shift, whatever happened in it.

RULE Y11.2  A block that is out of use.
When slot_grid_calendar.csv seals a block for a slot, or says it
is not in service, or the block has no capacity at all, the whole
capacity is published as unavailable, the reserved figure is zero
and the available figure is zero. The occupied figure is still
the boxes that stood there.

RULE Y11.3  A block that is in use.
The free capacity is the capacity less the boxes standing there
at the close of that slot. The reserved figure is the standing
credit, at the close of that slot, of every reservation covering
that block and slot, capped at the free capacity. The available
figure is the free capacity less the reserved figure, and never
below zero.

RULE Y11.4  Utilisation.
The utilisation of a block is its closing count over its
capacity, published at exactly nine decimal places. A block with
no capacity has a utilisation of 0.000000000 and is published
with it.

RULE Y11.5  Slot accounting.
Every slot of the shift is published with its event count, its
admitted count, its set aside count and its confirmed count, a
slot in which nothing happened included. Events belonging to no
slot are published on a row of their own under the not supplied
marker, after every slot.

PUBLISHES  yard_capacity.csv, yard_reservations.psv,
block_utilization.csv, slot_accounting.csv
