# Stage P11, the deadline correction

This stage tries to serve the reefers the reconciliation left short
of their mandatory floor at the vessel cutoff.

RULE P11.a  The required energy of a reefer is the sum of its stored
interval floors over the intervals of its lattice at or below its
cutoff interval. What it was served is the same sum restricted to
the intervals it is powered in. The shortfall is the difference,
never below zero. The shortfall intervals are the intervals of its
lattice at or below its cutoff it is not powered in.

RULE P11.b  The allowance an earlier stage placed is discretionary
energy and it does not count toward the mandatory floor.

RULE P11.c  The correction is worked as a sequence of sweeps. In a
sweep the reefers standing short are taken with the vessel critical
ones first and the rest after, each group in rank order. A reefer is
vessel critical when a priority override notice of this operating
day names it. A vessel critical reefer overturns an ordinary queue
position.

RULE P11.d  A short reefer looks at the intervals of its lattice at
or below its cutoff that it is not powered in, in ascending order,
and takes the first one that admits a displacement. It takes at most
one displacement per sweep.

RULE P11.e  A candidate to be displaced is a reefer powered on the
same feeder in that interval, that is neither vessel critical nor
frozen, and that holds more powered intervals at or below its own
cutoff than the dependency protection depth of
dispatch_operations_memo.pdf. The candidate carrying the highest
rank is displaced.

RULE P11.f  A displacement that raises the load of the feeder is
admitted only when the raised load stands at or below the adjusted
capacity plus the battery support of that interval. A displacement
that does not raise the load is always admitted.

RULE P11.g  An interval offering no candidate publishes a correction
state of refused_protected. An interval whose candidate would raise
the load beyond what P11.f admits publishes refused_no_headroom. A
displacement that is applied publishes corrected.

## Published document

deadline_correction.csv.
