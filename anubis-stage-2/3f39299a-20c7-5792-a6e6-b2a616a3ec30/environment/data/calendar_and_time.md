# Calendar and time

This document covers cooperative time, the allocation weeks, which week an instant belongs to,
and the moment at which each week is allocated. The layouts of `season_calendar.csv` and
`cooperative_time.json` are in record_dictionary.md.

## Instants in the record files

Every timestamp in the record files carries its own UTC offset, written either as a numeric
offset `+HH:MM` or `-HH:MM` or as `Z` for UTC, and stands for exactly the instant it writes.

## Cooperative time

The season calendar is written in cooperative wall-clock time, without offsets. Cooperative time
is not a fixed offset: it moves with daylight saving, and `cooperative_time.json` lists its
periods. Each period gives the first wall-clock time it governs (`from_local`) and the UTC offset
of cooperative time during the period (`utc_offset`). A wall-clock time belongs to the latest
period whose `from_local` is at or before it, and it stands for the instant obtained by reading it
at that period's offset.

## The season calendar

`season_calendar.csv` has one row per allocation week, in calendar order. Each week opens exactly
at the previous week's closing cutoff, and `closes_at` gives its closing cutoff.

The season window runs from the opening cutoff of the first week to the closing cutoff of the
last week.

## Which week an instant belongs to

A week covers every instant after its opening cutoff, up to and including its closing cutoff. An instant at or before the opening cutoff of the first
week, or after the closing cutoff of the last week, belongs to no week and lies outside the
season.

The same rule places every kind of instant in the extract: an order's placement instant, a
receipt's arrival instant and the effective instant of an identity event.

## The allocation instant

Each week is allocated once, at its closing cutoff, after every order, receipt and identity event
belonging to the week is known. That closing cutoff is the week's allocation instant. Wherever
these documents speak of something in force at a week's allocation, they mean in force at that
instant.
