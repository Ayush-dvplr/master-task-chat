STAGE Y07  Move admission
shift KP-2042-S23

This stage settles every canonical event against the yard as it
stood immediately before that event. It is walked in canonical
event order and it is stateful: an event is judged against the
state its predecessors left, and never against the state a later
event will produce.

RULE Y07.1  The ladder.
The rungs of move_admission_ladder.txt are put to an order in the
order that paper prints them. The first rung that catches an
order settles it and the remaining rungs are not put to it. The
printed order is not the alphabetical order of the rung codes.

RULE Y07.2  Waivers.
An exception of operational_exception_notices.csv that names this
shift and is not withdrawn lifts one rung for the order it
targets. A zone_waiver lifts the sealed zone rung, a tier_waiver
lifts the tier rung and a reservation_release lifts the reserved
capacity rung. A lifted rung is skipped for that order and the
rungs below it are still put to it. A cutoff_waiver lifts nothing
here and is read at the eligibility stage. A waiver never revives
a destination the topology does not carry: when the tier rung is
lifted for an order whose destination block is not in force, the
rungs below it read that block as holding no capacity at all, so
the reserved capacity rung catches the order.

RULE Y07.3  Reserved capacity is settled before free capacity.
At the reserved capacity rung, take the block's capacity less the
boxes standing in it at that instant. That is the free capacity.
Then withhold, from that free capacity, the standing credit of
every reservation that covers this block and this slot and names
a service group other than the service group of this order's box.
What remains is what this order may be placed against. When what
remains is zero or less the rung catches the order. A stage that
counts free capacity and admits the order against it, without
first withholding the reserved credit, has read this backwards
and will admit orders this terminal refuses.

RULE Y07.4  What a reservation withholds.
A reservation of hold_reservation_notices.jsonl counts when it
names this shift and its state is held. Its opening credit is the
quantity it asks for, and a quantity written as the not supplied
marker asks for the whole opening free capacity of its block. The
credit is then capped at that opening free capacity, and whatever
was asked beyond it is published as unmet and withholds nothing.
A reservation stands over every slot from its first slot to its
last slot, both included.

RULE Y07.5  What consumes a reservation.
An admitted order whose box belongs to the service group a
standing reservation names consumes one unit of that
reservation's remaining credit. Where more than one such
reservation stands, the one with the lowest reservation_id is
consumed. An order of any other service group consumes nothing,
which is why the credit it was bound by is still standing for the
orders that follow it.

RULE Y07.6  The tier rung.
A placement at exactly the maximum legal tier of the applicable
geometry is lawful. A placement one tier beyond it is not. A
destination block that is not in force, or whose capacity is
zero, is caught by this rung as well.

RULE Y07.7  The duplicate rung.
The duplicate rung is the last rung. Among the orders of one
cluster, the canonical one is the first in canonical event order
that no earlier rung caught, and every later member of that
cluster is caught here. So an order that carries an unknown box
and is also a duplicate is set aside as an unknown box, and a
cluster whose first member is caught by an earlier rung has its
second member as its canonical one.

RULE Y07.8  A set aside order changes nothing.
An order the ladder catches moves no box, occupies no slot,
consumes no reservation and frees no capacity. It stays in the
published record, and the capacity a set aside order would have
released is never counted as released.

PUBLISHES  move_eligibility.csv, rejected_moves.tsv,
rejection_reasons.csv, accepted_moves.csv
