# Legal Hold Questions and Answers

**Q1. Where are holds recorded?**
In `legal_holds.psv`, one event per line: event id, collection, action (`PLACE` or `RELEASE`),
effective time stamp, matter reference.

**Q2. On which date does an event count?**
On the calendar date of its effective time in Indian Standard Time (UTC+05:30). Time stamps
written with `Z` are in UTC and must be moved to IST before the date is taken; a `RELEASE` at
20:10 UTC counts on the next IST day. An event counts for an as_of date when its IST date is
on or before that date.

**Q3. Which event is the last one on a date?**
When two events of one collection count on the same date, a `PLACE` comes after any `RELEASE` of that date, so the hold stands. Between events of the same action on one date, the event with the higher event id comes later.

**Q4. Do holds expire?**
Holds expire 365 days after they are placed unless renewed.

**Q5. Who may release a hold?**
Only the legal cell, through a `RELEASE` line quoting the matter reference.
