# Stage P06, the feeder reconciliation and the spill

This stage withholds the standing reserve and unpicks the placements
the reserve no longer admits.

RULE P06.a  The reserved capacity of a feeder in an interval is its
nominal capacity for that interval less its standing reserve watts,
and never below zero. The reserve is withheld before any free
capacity is counted.

RULE P06.b  The intervals are worked in ascending order. Within an
interval, while the load of a feeder stands above its reserved
capacity, the powered reefer of that feeder carrying the highest
rank is removed.

RULE P06.c  A removed placement spills to the next eligible
interval: the lowest interval of the lattice of that reefer that is
above the interval it was removed from, that the reefer does not
already hold, and where the load of the feeder plus the draw of that
interval stands at or below the reserved capacity. It does not move
to the cheapest interval of the day.

RULE P06.d  A removed placement that finds no such interval
publishes a target interval of zero and a spill state of unspilled.
Every other removal publishes its target interval and a spill state
of spilled.

RULE P06.e  A violation row is published for every feeder and
interval where a removal happened, carrying the load standing before
the removals, the reserved capacity, the excess and the number of
removals.

RULE P06.f  The load state of a feeder and interval reads
over_capacity above the capacity it is taken against, at_capacity
at it and clear below it. The load ledger of this stage takes it
against the reserved capacity, and the removals of RULE P06.d
leave no feeder and interval of that ledger above its reserved
capacity, so only the lower two readings appear there.

## Published documents

feeder_load_ledger.csv, feeder_violation_ledger.csv and
spill_decisions.tsv.
