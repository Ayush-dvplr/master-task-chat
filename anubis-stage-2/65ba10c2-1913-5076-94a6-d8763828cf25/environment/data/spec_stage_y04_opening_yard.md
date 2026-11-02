STAGE Y04  The opening yard
shift KP-2042-S23

This stage materialises the yard as it stood when the shift
opened.

RULE Y04.1  Which blocks are in force.
yard_topology.xml names the blocks in force for this shift. A
block the topology does not name takes no part in this shift
however many rows the geometry register carries for it.

RULE Y04.2  The applicable geometry.
In block_geometry_register.csv set aside rows of another shift,
rows marked retired and rows marked future. The applicable
revision of a block is the surviving row with the highest
revision_seq. A block in force with no surviving revision has
zero rows, zero tiers and zero capacity.

RULE Y04.3  Capacity.
The slot capacity of a block is its rows multiplied by its
maximum tier. A block whose capacity is zero is published with a
capacity of zero. That is a different published state from a
block the topology does not carry, which is published not at
all.

RULE Y04.4  The opening stack.
A row of stack_inventory_snapshot.csv places a box only when its
stack_state is stacked, its block is in force and its box has an
applicable master record. Every other row places nothing; a box
it names is off the yard at the opening instant and has no yard
position.

RULE Y04.5  An empty block.
A block in force that the opening stack places nothing into is
published with an opening count of zero and its whole capacity
free. It is never left out of the published occupancy.

PUBLISHES  initial_occupancy.psv
