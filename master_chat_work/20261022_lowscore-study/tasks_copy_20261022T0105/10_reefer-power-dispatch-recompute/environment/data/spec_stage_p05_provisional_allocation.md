# Stage P05, the provisional allocation

This stage places the queue against the nominal capacity of the
feeders, interval by interval. It is a local settlement and later
stages unpick part of it.

RULE P05.a  The nominal capacity of a feeder in an interval is the
nominal capacity watts of its governing capacity row.

RULE P05.b  An interval covered by a booked maintenance window
against the feeder carries a nominal capacity of zero.

RULE P05.c  The governing derating notice of a feeder is its
applicable notice carrying the highest notice sequence. Over the
intervals from its first interval to its last interval inclusive the
nominal capacity is multiplied by the derate permille, divided by a
thousand and floored. Outside that span the notice does nothing.

RULE P05.d  The draw of a reefer in an interval is the whole watt
figure stage P03 stored for it under P03.i.

RULE P05.e  Within an interval the queue is walked in rank order.
A reefer is powered when the running load of its feeder plus its own
draw is at or below the nominal capacity, and held otherwise. A load
equal to the capacity is lawful. Only a load above the capacity is a
violation.

RULE P05.f  A reefer held in an interval is not reconsidered in that
interval. The standing reserve is not withheld at this stage.

## Published document

provisional_allocation.psv, one row per reefer and interval of its
lattice.
