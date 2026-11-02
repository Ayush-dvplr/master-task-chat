# Stage P02, the availability lattice

This stage places every reefer on the interval grid.

RULE P02.a  The grid carries 96 intervals of 15 minutes. Interval n
covers the minutes from 15 times n minus 15 inclusive to 15 times n
exclusive.

RULE P02.b  A connection window runs from the connect minute
inclusive to the disconnect minute exclusive. An interval belongs to
a window when the two overlap in at least one minute.

RULE P02.c  A disconnection landing exactly on an interval boundary
closes the interval before it and does not open the interval that
starts there. A connection landing exactly on an interval boundary
opens that interval, so a window whose disconnect minute equals its
connect minute covers no interval at all.

RULE P02.d  An interval covered by a booked maintenance window
against the feeder of the reefer, or against the plug of the reefer,
is struck out of the lattice of that reefer. A window whose state
reads cancelled strikes nothing out.

RULE P02.e  The window state of a reefer reads empty when its
lattice holds no interval, single_slot when it holds exactly one and
open otherwise. A reefer with an empty lattice publishes a first and
a last interval of zero.

RULE P02.f  The interval demand of a feeder in an interval counts
every reefer whose lattice holds that interval and sums their stored
nameplate watts. The count is taken before the admission ladder runs.

## Published documents

availability_lattice.csv and interval_demand.csv.
