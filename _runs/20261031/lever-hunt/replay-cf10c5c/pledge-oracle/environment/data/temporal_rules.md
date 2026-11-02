# Temporal rules

## Zones and offsets

Each holder carries a business zone. zone_offset_table.csv gives the offset in
minutes east of the prime meridian for a local effective period. The period is
keyed by local dates and is half open, so a local date equal to the lower bound
belongs to that row and a local date equal to the upper bound belongs to the next
row. A local wall time converts to an instant by subtracting the offset that the
table gives for the local date of that wall time.

Two zones change their offset during the settlement window. The zone that a
pledge uses is the business zone of its holder.

An instant reads as a local date by adding the offset in force at that instant.
That offset belongs to the latest local effective period whose starting local date,
converted back to an instant, falls at or before the instant in question.

## Business days

A local date is a business day when the following layers, read from the top, give
an open verdict at the first layer that speaks about that date.

| layer | source | effect field |
| --- | --- | --- |
| 1 | counterparty_closure_overrides.csv | effect |
| 2 | business_day_exceptions.csv | effect |
| 3 | zone_holiday_calendar.csv | observed |
| 4 | weekday rule | Monday to Friday are open |

A closure override names a holder and a local date and carries either closed or
open. A business day exception names a zone and a local date and carries open. A
holiday row names a zone and a local date; an observed holiday closes that date.

## Due expressions

A register entry, an amendment and a series definition all carry a due
expression drawn from this closed set. Every expression resolves against the
origin instant of the pledge read in the business zone of its holder.

| expression | meaning | local time of day |
| --- | --- | --- |
| D+n | n calendar days after the origin local date | 17:00 |
| BD+n | n business days after the origin local date | 17:00 |
| EOM | the last business day of the origin local month | 17:00 |
| NBDk | the k th business day of the month after the origin local month | 12:00 |
| FIXED:stamp | the local wall time written in the expression | as written |

A FIXED expression carries a local wall time without an offset. It is read in the
business zone of the holder.

## Minutes

Lateness is the count of whole minutes from the governing due instant to the
effective instant, taken on the instants themselves and truncated toward zero. An
effective instant at or before the due instant gives zero. lateness_rounding_cases.csv
records closed figures for stated pairs of instants.

Rates are reported in parts per thousand. A rate is computed once, at the final
stage, from integer counts, and a half is carried upward.
