# Meeting cost chargeback

Every occurrence of the settled schedule is charged to the office that hosts it
and allocated to the collection that holds it. The chargeback reports rollups
only; there is no per line ledger.

## Lines

There is one line per occurrence of the settled schedule and per required
attendee of that occurrence. The rate of the line is the attendee's rate in
force (office-register.md) on the UTC date of the settled start of the
occurrence.

Stage 1, base cents. The base amount of a line is the rate in cents per hour
multiplied by the duration of the occurrence in seconds and divided by 3600,
rounded to a whole number of cents half up.

Stage 2, converted cents. The converted amount of a line is its base amount
multiplied by the conversion basis points of the occurrence office
(governance-schedule.md) and divided by 10000, rounded to a whole number of
cents half up.

Each line is rounded at each stage before the next stage reads it; the stages
are never carried at full precision and rounded once.

## Office rollup

For each office, the rollup holds the number of lines, the sum of the base
amounts, the sum of the converted amounts and the basis points used.

## Collection allocation

The converted total of an office is allocated across the collections that hold
occurrences in that office, in proportion to each collection's share of the
office's base total (the base amounts of the lines of that collection in that
office). Each collection first receives the whole part of
`converted total times collection base divided by office base`. The cents left
over are then given out one at a time to the collections with the largest
fractional parts, the smaller collection id winning a tie, until the allocated
amounts add up to the converted total exactly.

Worked example. An office converted total of 1001 cents is shared by
`cal-alpha` with base 300 and `cal-beta` with base 700, base total 1000. The
whole parts are 300 (fraction 0.3) and 700 (fraction 0.7); one cent is left
over and goes to `cal-beta`, giving 300 and 701.
