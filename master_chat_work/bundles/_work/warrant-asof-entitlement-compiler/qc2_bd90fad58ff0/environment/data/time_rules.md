# Time rules

## Instants

An instant is written exactly `YYYY-MM-DDTHH:MM:SS` followed by `Z` or by an offset `+HH:MM` or `-HH:MM`, with a real calendar date, hours 00 to 23 and minutes and seconds 00 to 59. Nothing else is an instant: a space instead of `T`, a missing offset, fractional seconds, a lower case `z`, an offset without its colon and an impossible date are all unreadable, and a record carrying one in a field the compiler must read is rejected `bad_timestamp`. Offsets are exact: `2026-10-28T15:30:00-04:00` and `2026-10-28T19:30:00Z` are the same instant.

Epoch fields are a decimal integer, as text or as a JSON integer. Their unit is fixed per file (`corpus_index.md`); `recorded_at` means seconds in `grant_corrections.jsonl` and milliseconds in `revocations_selfservice.csv`. A record is visible when its recorded instant is at or before the cutoff at the precision it was written with.

Every instant the compiler writes is UTC in the form `YYYY-MM-DDTHH:MM:SSZ`.

## Dates

A date is written exactly `YYYY-MM-DD` and must exist. HR `effective_date` values name the calendar day on which an event takes effect. Which clock that day is read on is the gateway's convention, and the reviewer observations record what the gateway did on such days. Contract `start_date` and `end_date` are read on the same clock as HR dates, using the contract's own `site` where that clock is a site's; a contract covers its whole `end_date`, so cover runs from the start of `start_date` to the start of the day after `end_date`. On-call `week_start` and `shift_date` are local dates in the rotation's zone.

## Zones

Zone arithmetic uses `tz_rules.json` and nothing else. A zone has a standard offset, a daylight offset and a list of transitions, each a UTC instant and the kind of time in force from that instant. The offset in force at an instant is that of the latest transition at or before it; before a zone's first transition the other kind is in force. A zone without transitions always uses its standard offset. A local wall time converts to the UTC instant whose offset in force, added to it, gives back that wall time. When two such instants exist the earlier is used; when none exists the standard offset is applied.

## Windows

Windows in this corpus, whether a membership, a binding, a grant, a shift, a freeze window or a contract's cover, all follow the same boundary convention, the one the gateway enforces and the reviewer observations show. A key value states the instant at which the permission stops being in effect under that convention.
