# Stage P07, the crane adjusted capacity

This stage merges the crane records into the feeder capacity. A
crane changes the capacity available to reefers. It is not an extra
load added to the reefer load.

RULE P07.a  A crane duty of this operating day counts when the
confirmation carrying the lowest confirm sequence for that crane and
interval reads landed. A duty whose lowest confirmation reads
cancelled draws nothing, and so does a duty with no confirmation at
all.

RULE P07.b  A crane covered by a booked maintenance window in an
interval draws nothing in that interval.

RULE P07.c  The crane draw of a feeder in an interval is the sum of
the demand of its counting duties, converted from kilowatts to watts
through the demand entry of the unit register.

RULE P07.d  The adjusted capacity of a feeder in an interval is its
reserved capacity less its crane draw. A difference below zero is
clamped to zero and publishes a clamp state of clamped. Every other
interval publishes a clamp state of clear.

## Published document

crane_adjusted_capacity.csv.
