# Calendar rules

## Regional clocks

`region_clock.ini` gives each region a standard offset and a daylight offset
in minutes east of UTC, and the UTC spans during which the daylight offset
applies. A span `start/end` covers instants at or after `start` and before
`end`. The local time of a UTC instant in a region is the instant plus the
offset in force at that instant. A local wall time on a date is converted to
UTC with the offset that is in force at the resulting UTC instant.

Every local time and local date of a lease is read on the clock of its
booking region, even after the lease has moved to a branch of another region.
That covers the knowledge instant of each snapshot and the local date of a
servicing ledger posting (`cash_rules.md`).

## Business days

A business day of a region is a Monday to Friday that is not a holiday of that
region. A holiday is a `VEVENT` of `holiday_calendar.ics` with
`STATUS:CONFIRMED` whose `CATEGORIES` list names the region; it covers every
date from `DTSTART` up to but not including `DTEND`. Events with any other
status are not holidays. Due dates are rolled on the business days of the
lease's booking region.

## Roll of due dates

An instalment whose nominal due date (`schedule_rules.md`) is not a business
day is due on a business day chosen by the business day convention of its
lease agreement. Agreements of the two contract segments carry different
conventions, and every agreement of one contract segment carries the same
one. The printed due dates in `invoice_notices.csv` were produced by the
governing conventions and are the record of them: one convention per contract
segment reproduces every printed date, and the same conventions govern every
instalment of every lease, printed or not.
