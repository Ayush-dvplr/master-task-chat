# S02 availability construction

Availability is per aperture and is built once, before any pass is
looked at.

Start from aperture_service_windows.csv. Take only the rows whose
service_state is in_service. Each row is a half open interval
[effective_from_s, effective_to_s). Normalise the set: sort it, merge
any two intervals that overlap or abut, and drop any interval of zero
length.

Subtract maintenance_dockets.csv for that aperture. Each docket is the
half open interval [start_s, end_s).

Subtract blackout_advisories.psv for the station the aperture belongs
to. Each advisory is the half open interval [start_s, end_s). A blackout
applies to every aperture at the station.

The result is the availability set of the aperture: a sorted list of
disjoint half open intervals. Subtraction is exact interval arithmetic
on integer seconds. A cut that lands exactly on an edge removes nothing:
a docket [b, c) does not touch an availability interval [a, b).

An aperture whose service_state is withdrawn for a stretch contributes
no availability over that stretch. An aperture that is withdrawn for a
whole settlement period has an empty availability set in that period,
which is what produces an empty utilisation denominator at S11.

## the accounting period window

station_accounting_calendar.csv carries one row per station per period
per accounting day. The station local accounting period is the interval
from the smallest local_open_s of its rows to the largest local_close_s
of its rows, for that station and that period, and it is half open. The
period windows of a station are contiguous and do not overlap.

Because the offsets differ by station, the same instant sits in P1 at one
station and in P2 at another. Every period question in this pipeline is
asked against the calendar of the station that owns the aperture.
