# Conflicts and settling

## Conflicts

Two occurrences are compared when they share at least one required attendee
(identities-and-aliases.md). Order the pair by absolute start instant and then
by occurrence identifier; the first member of the pair is the earlier one.

The travel buffer is the `buffer min` of the settling parameters in force
(governance-schedule.md). It is applied to the end of the earlier occurrence,
and only when the two occurrences carry different office codes. It is never
applied to the start of the later occurrence and it is never applied inside a
single office.

The effective end of the earlier occurrence is its end instant plus the buffer
when the buffer applies, and its end instant otherwise. The pair is a conflict
when the effective end of the earlier occurrence is strictly later than the
start of the later occurrence; an effective end exactly equal to the start of
the later occurrence is not a conflict. The overlap is reported in whole
minutes, rounded down, as the difference between the effective end and the
later start.

Two occurrences of one series that overlap each other are a pair like any
other. The conflict report describes the schedule before settling.

## Escalation ranks and pins

The escalation rank of an occurrence is the rank of its series class in the
class rank table, read at the effective revision; a class with no usable row
takes the `default rank` of the settling parameters. A higher rank means the
occurrence is harder to move.

An occurrence is pinned when its rank is greater than or equal to the `pin
rank` of the settling parameters, or when the master component of its series
carries the property `X-PINNED` with the value `TRUE`. A pinned occurrence is
never deferred.

## The settling loop

Settling is a bounded fixpoint. The quantum is the `quantum min` and the round
cap is the `round cap` of the settling parameters.

At the start of a round the conflict set is recomputed over the current
schedule. When it is empty the pass has converged and stops; the round counter
is not advanced and the stop reason is `clear`.

Otherwise, if the round counter has already reached the cap, the pass stops
without converging, reports the remaining pairs as residual conflicts, and the
stop reason is `cap`. This is a normal outcome and not an error.

Otherwise, if every pair in the set has two pinned members, nothing can move:
the pass stops without converging, the round counter is not advanced, the
remaining pairs are reported as residual conflicts and the stop reason is
`pinned`.

Otherwise the round counter advances and the pass selects, among the pairs that
have at least one member that is not pinned, the pair whose earlier member has
the smallest absolute start instant, breaking ties by the first identifier and
then by the second identifier. When exactly one member of that pair is pinned,
the other member is deferred whatever the two ranks are. Otherwise the
occurrence with the lower escalation rank is deferred, and when both ranks are
equal the occurrence with the larger occurrence identifier is deferred.

Deferral is applied to the wall clock. Convert the current start of the
deferred occurrence to a wall clock value in the zone of its own office, add
the quantum in wall clock minutes, then resolve the result back to an absolute
instant with the rules of zone-rules.md. A deferral can land inside a forward
transition, in which case the resolution shifts it further and the extra shift
is recorded. The new end is the new start plus the duration in seconds of that
occurrence; durations are fixed once, before settling begins, and are not
recomputed. Amendment A5 changes what happens when a deferral overruns the
working day.

Each deferral appends a move recording the round number, the occurrence
identifier, the start before and after the move, the deferred minutes, the
extra gap shift in minutes and the pair that caused the move.

## Which schedule feeds which report

The conflict report and the load fold are computed from the schedule before
settling. Attendance, travel blocks, busy conflicts and the chargeback are
computed from the schedule after settling.
