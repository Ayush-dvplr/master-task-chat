# The calibration slice

Four properties of this platform are not written down anywhere in the reference
set, and a fifth is written down but easy to read the wrong way round. Rather
than publish them, the platform publishes a small window it has already settled,
together with the figures that window produced. Any reading of the platform that
reproduces every published figure is the platform. Exactly one does.

## What is published

The calibration file in this working set carries two things. The first is a
complete miniature working set: its own window, its own channel, domains, feeds,
producers, identity events, rate cards, incidents, landing records, exceptions
and policy figures, in exactly the same shape as the registers of the window you
have been asked to settle. The second is the set of figures that miniature
window produced when the platform settled it.

The miniature working set is not part of the window you are settling. It shares
no identifier with it and contributes nothing to it. It is there to be settled
in its own right, as many times as you need, under whatever reading of the
platform you are testing.

## The figures that were published

For the calibration window the platform published how many of its records were
curated, how many were withdrawn and how many were quarantined; the payload
units it curated; the charge it settled, in total and for each of its settled
domains; the feeds it quarantined; how many records were withdrawn under each
reason; and the settled unit rate of a handful of named individual records.

The record level figures are the sharpest instrument. Each is the unit rate that
one named record finished at, in micros, after everything that bore on it had
been applied. Some of those records sit on feeds that were comfortably inside
their nominal throughput and some sit on feeds that were well over it, which is
not an accident.

## The properties being pinned down

The window summary you produce has to state what you concluded, using these
names and these legal values.

`adjustment_precedence` is a sequence containing each of `abatement`,
`override`, `rebate` and `surcharge` exactly once, in the sequence the platform
composes them.

`backpressure_coefficient_micros` is a whole number from zero to six hundred
inclusive.

`quantisation_step_micros` is one of `5`, `10`, `20`, `25`, `40`, `50`, `80`,
`100` or `125`.

`rounding_mode` is one of `ceil`, `floor`, `half_down`, `half_even` or
`half_up`, naming the convention the platform uses for a value that falls
between two grid points. Under `ceil` the value goes to the grid point above and
under `floor` to the one below, whichever side it fell on. Under `half_up` a
value exactly halfway goes to the grid point above and under `half_down` to the
one below, and otherwise both go to the nearer point. Under `half_even` a value
exactly halfway goes to whichever of the two grid points is an even multiple of
the grid spacing, and otherwise to the nearer point.

`tombstone_reading` is either `retroactive` or `forward`. This one is not a
secret: the retention rulebook says which reading this platform uses, in terms.
It is stated here as a value you must report because it is the single reading
that most changes what a window settles to, and because the calibration figures
will confirm it independently of the prose.

## Sufficiency

The published figures admit exactly one combination of those five values. Fewer
figures would have admitted several, and the platform publishes as many as it
does for that reason. If a reading of the platform reproduces some of the
published figures but not all of them, it is not the platform, however close it
looks.
