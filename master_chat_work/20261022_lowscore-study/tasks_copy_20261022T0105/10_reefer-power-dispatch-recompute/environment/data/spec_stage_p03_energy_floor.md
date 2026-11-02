# Stage P03, the mandatory energy floor

This stage settles the energy each reefer must take to hold its
temperature, interval by interval.

RULE P03.a  The ambient class of an interval is the ambient class the
interval readings of ambient_condition_returns.json carry for this
operating day.

RULE P03.b  The ambient multiplier of a reefer in an interval is the
multiplier the multiplier table carries for the pairing of the
temperature class of the reefer and the ambient class of the
interval.

RULE P03.c  A pairing the multiplier table carries no row for falls
back to the class default multiplier the same paper carries. An
absent pairing is a fallback to that default and it is not a
multiplier of zero.

RULE P03.d  The maintenance coefficient of a temperature class is
the numerator and denominator the governing sheet of
substation_capacity_workbook.xlsx carries for that class.

RULE P03.e  The floor of a reefer in an interval is its stored
nameplate watts, taken over a quarter of an hour, multiplied by the
ambient multiplier and by the maintenance coefficient, rounded half
up and stored as a whole watt hour. The rounding happens once per
interval and the stored whole numbers are what the mandatory floor
sums.

RULE P03.f  The mandatory floor of a reefer is the sum of its stored
interval floors over its lattice.

RULE P03.g  The requested energy of a reefer is its declared energy
when a return declared one, and its mandatory floor otherwise. The
floor state reads declared in the first case and defaulted in the
second.

RULE P03.h  The discretionary energy of a reefer is its requested
energy less its mandatory floor, and never below zero.

RULE P03.i  The draw of a reefer in an interval is its stored
nameplate watts multiplied by the ambient multiplier and by the
maintenance coefficient, rounded half up and stored as a whole watt.
The interval floor and the interval draw are two roundings of the
same quantity, taken over a quarter of an hour and over the hour, so
the draw is rarely four times the floor and neither is derived from
the other.

## Published document

energy_floor_ledger.csv.
