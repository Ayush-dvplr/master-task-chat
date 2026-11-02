# Attendance

Attendance is computed from the settled schedule, for every required attendee
of every occurrence, in the effective office of that attendee for that
occurrence (travel-and-busy.md). The local start date is the date of the
occurrence start on the wall clock of the effective office, and the office row
in force for that date is chosen as office-register.md describes.

## Closures

The closure database named by the index (role `closures`) holds the table
`closures(office, day, name, revision, state)`. A closure may be recorded more
than once for one office and day; the row with the greatest `revision` is in
force, and when that row's `state` is `withdrawn` the office is open that day.
Any other state means the office is closed.

## Violations

A violation of kind `office-holiday` is recorded when the local start date is
a closure day of the effective office. Its `minutes_outside` value is zero.

A violation of kind `non-working-day` is recorded when the office row in force
for the local start date has `working` equal to `N`. Its `minutes_outside` value
is zero.

A violation of kind `outside-working-window` is recorded when the occurrence
starts before the opening minute of the working window of the row in force, or
ends after its closing minute. Both minutes are wall clock minutes in the zone
of the effective office, counted from local midnight of the local start date:
the start minute is the wall clock start less that midnight, and the end minute
is the wall clock end less that same midnight, where each whole day between the
two local dates counts as 1440 minutes. An occurrence that runs past midnight
therefore has an end minute greater than 1440. The reported `minutes_outside`
is the larger of the opening minute minus the start minute and the end minute
minus the closing minute.

Several kinds can fire for the same occurrence and every kind that fires is
recorded. Amendments A2 and A4 change how closures and non working days
interact with the working window test.
