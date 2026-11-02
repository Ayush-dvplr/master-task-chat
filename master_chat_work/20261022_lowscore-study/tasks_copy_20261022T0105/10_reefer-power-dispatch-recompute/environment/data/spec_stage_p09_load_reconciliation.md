# Stage P09, the load reconciliation passes

This stage settles how much discretionary energy each reefer is
allowed out of the day headroom of its feeder, and then places that
allowance into intervals.

RULE P09.a  The headroom of a feeder in an interval is its adjusted
capacity plus its battery support less its reconciled load, and
never below zero. The day pool of a feeder is the sum of its
interval headroom watts divided by four and floored.

RULE P09.b  The members of a feeder are its queued reefers carrying
a discretionary energy above zero. A pass settles every member of a
feeder together, so their order within the pass settles nothing.

RULE P09.c  Every share opens at zero. The reconciliation runs the
number of passes the pass budget of dispatch_operations_memo.pdf
names. The budget is spent whether or not the shares have settled.
It is not a guard on a convergence loop.

RULE P09.d  Within a pass the need of a member is its discretionary
energy less its standing share, never below zero. The unallocated
pool is the day pool less the sum of the standing shares.

RULE P09.e  When the unallocated pool and the total need both stand
above zero, the target of a member is its standing share plus the
unallocated pool multiplied by its own need and divided by the total
need. Otherwise the target is the standing share.

RULE P09.f  The limit of a member is the lesser of its discretionary
energy and the share ceiling the governing workbook sheet carries
for its vessel. A target above the limit is cut to the limit and the
difference is freed.

RULE P09.g  What a limit frees is redistributed inside the cross
classification of substation and service group, among the members of
that cell whose target stands below their own limit, in proportion
to the room each has left. It is not spread across the whole feeder.

RULE P09.h  The share is then damped: the closing share is the
standing share plus the damping fraction of the difference between
the target and the standing share. The damping fraction is the
numerator and denominator the governing workbook sheet carries.

RULE P09.i  A pass that would move a share by less than the minimum
step of dispatch_operations_memo.pdf moves it by the minimum step
instead, in the direction it was moving.

RULE P09.j  The pass closes by rounding the share half up to a whole
watt hour and holding it between zero and the limit. The pass after
it opens from that rounded share.

RULE P09.k  A pass row publishes a pass state of moving when its
closing share differs from its opening share and settled otherwise.

RULE P09.l  The allowance of a reefer is placed after the last pass.
The queue is walked in rank order and each reefer fills its share
from the earliest interval of its lattice onward, taking from each
interval no more than the headroom watt hours left there. What no
interval could take is the unplaced allowance.

RULE P09.m  The final load of a feeder in an interval is its
reconciled load plus four times the allowance placed there.

## Published document

reconciliation_iterations.csv, one row per pass, feeder and member.
