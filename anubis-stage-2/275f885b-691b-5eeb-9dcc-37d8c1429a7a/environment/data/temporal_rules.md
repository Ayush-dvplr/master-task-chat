# Temporal rules

## Time bases

`source_declarations.properties` declares the time base of every source. Requisition
timestamps are depot local wall clock readings with no offset written on them. Dispatch
records, amendment notices, visit events, release certificates and every `issued_at` are
universal time. Registry observations and the date fields of reference tables are calendar
dates. Lot expiry is a depot local wall clock reading.

## Depot clocks

`depot_clock_offsets.csv` declares the offset from universal time in minutes for one depot on
one calendar date. Where a depot and date carry more than one declaration, the one with the
latest `issued_at` is in force. Converting a depot local reading to universal time subtracts
the offset declared for the depot on the calendar date of that reading. A depot and date with
no declaration leaves the export incomplete.

## Round windows

The claim window of a round opens at the local time declared as `day.start.local` on the start
date of that round and runs for the number of days declared as `window.length.days`. The window
is half open: a reading at the opening instant falls inside it and a reading at the closing
instant falls outside it.

## As of limits

A requisition is timely when its `effective_at` falls inside the claim window of the round it
names and its `recorded_at` falls strictly before the close of that window.

A dispatch record is in view for a claim when its `recorded_at` falls at or before the close of
the claim window of that claim, in universal time.

A campaign phase revision is in force for a region and round when its `issued_at` falls at or
before the opening instant of that round window, in universal time.

A registry observation is in view for a claim when its `observed_at` falls at or before the
calendar date on which the round window opens.
