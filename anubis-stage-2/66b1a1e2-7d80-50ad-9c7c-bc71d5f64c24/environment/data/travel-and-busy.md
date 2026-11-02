# Travel and busy periods

## Legs

The itinerary named by the index (role `itineraries`) lists flight legs
(tabular-conventions.md). Each confirmed leg has an id, an attendee, a
departure office with a wall clock value in that office's zone, and an arrival
office with a wall clock value in that office's zone. Both wall clock values are
resolved with the rules of zone-rules.md, so a departure can be ambiguous or
nonexistent like any other wall clock value.

The blocked window of a leg starts 120 minutes before the departure instant and
ends 90 minutes after the arrival instant, and it is half open at the end.

An occurrence is blocked when the attendee of the leg is one of its required
attendees and the occurrence interval intersects the blocked window. The kind is
`airborne` when the occurrence interval also intersects the flight interval,
which runs from the departure instant up to the arrival instant, and
`ground-buffer` otherwise. Every interval in this section, the occurrence
interval included, is half open at the end, so two intervals that only touch do
not intersect.

A leg crosses the date line when the number of whole days between the departure
local date and the arrival local date differs from the number of whole days
between the departure UTC date and the arrival UTC date. The two local dates are
the dates of the wall clock values exactly as written; the two UTC dates are
the dates of the resolved instants.

## Effective office

An attendee has a home office recorded in the attendee register. After a leg
arrives, that attendee is considered to be at the arrival office of the most
recent leg whose arrival instant is less than or equal to the instant being
tested. Before any leg arrives, the attendee is at the home office. For an
occurrence, the instant tested is the start instant of that occurrence in the
schedule being measured. The effective office decides which office row, which
solar window and which closures apply to that attendee for that occurrence.

## Busy periods

The busy database named by the index (role `freebusy`) holds the table
`periods(source, attendee, fbtype, start, finish, withdrawn)`. `start` is an
absolute instant. `finish` is either an absolute instant or a duration such as
`PT90M`, added to the start as exact elapsed time. A row whose `withdrawn` is
not zero was retracted and takes no part. A null `fbtype` counts as `BUSY`.

A period whose `fbtype` is `FREE` marks time the attendee has offered as
available; it is not a commitment and never produces a busy conflict. Every
other period is an external commitment that the executive assistant already
accepted; the schedule does not move it, it only reports which occurrences
collide with it.

Before the schedule is tested against them, the commitment periods of each
attendee are coalesced. Two periods of one attendee that overlap, or that touch
because one ends exactly where the other starts, merge into one period running
from the earlier start to the later end, whatever their busy types, and merging
repeats until no two periods of that attendee overlap or touch. A merged period
reports the busy type of highest precedence among the periods it absorbed:
`BUSY-UNAVAILABLE` first, then `BUSY`, then `BUSY-TENTATIVE`, then any other
value, among which the one that sorts first wins. Periods of different
attendees never merge.

A busy conflict is an occurrence of the settled schedule, a required attendee
of it and a coalesced period of that attendee whose interval intersects the
occurrence interval, both half open.
