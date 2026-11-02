# Durations

When the winning component carries `DTEND`, the duration in seconds is the
difference between the resolved `DTEND` instant and the resolved `DTSTART`
instant of that same component. The same number of seconds is added to the start
of every occurrence of the series. The duration source is `DTEND`.

When the winning component carries `DURATION`, the duration source is
`DURATION` and the store level `duration_semantics` setting decides the
arithmetic.

Under `exact` semantics a week counts as 604800 seconds and a day counts as
86400 seconds, and the whole duration is added to the absolute start instant.

Under `nominal` semantics the week and day parts are calendar quantities. The
start of the occurrence is converted to a wall clock value in the zone of the
occurrence office, the calendar days implied by the week and day parts are added
to that wall clock value at the same wall clock time, the result is resolved
back to an absolute instant with the rules of zone-rules.md, and only then are the
hour, minute and second parts added as elapsed seconds. Under `nominal`
semantics a duration that spans a transition is longer or shorter than the exact
reading by the size of that transition.

When the week and day parts are both zero there is nothing to add on the wall
clock: the hour, minute and second parts are added to the absolute start
instant directly, so such a duration behaves identically under both settings.

A component with neither `DTEND` nor `DURATION` lasts one hour.

The zone of the occurrence office is the `tzid` of that office in the office
register (office-register.md). The length of an occurrence supplied by an
RDATE period, and the length a ranged override hands forward, are set out in
additional-dates.md and amendments.md.

Worked example. Under `nominal` semantics an Adelaide occurrence starting
2027-04-03 09:00 local (+10:30, so 2027-04-02 22:30Z) with `DURATION:P1D`
ends at 2027-04-04 09:00 local. Adelaide has moved to +09:30 by then, so the
end is 2027-04-03 23:30Z and the occurrence lasts 90000 seconds. Under `exact`
semantics it lasts 86400 seconds.
