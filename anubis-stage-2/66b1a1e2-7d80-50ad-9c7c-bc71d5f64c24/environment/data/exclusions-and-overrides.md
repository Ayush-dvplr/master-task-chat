# Exclusions and overrides

An `EXDATE` property may carry several values separated by commas, and a
component may carry several `EXDATE` properties. Every value is resolved to an
absolute instant with the rules of zone-rules.md, using the `TZID` of its own
property, and is matched against original instants. A value that matches an
original instant is applied and the occurrence disappears. A value that matches
nothing is recorded as unmatched and changes nothing.

Exclusions are applied before overrides are matched. An override component
carries `RECURRENCE-ID`. Its value is resolved to an absolute instant and
matched against the original instants that remain once the exclusions are
applied. A value that matches nothing, including a value that names an excluded
instant, is an orphan; the override is rejected, is recorded with the reason
`orphan-recurrence-id`, is excluded from the schedule, and does not add to the
length of the series.

An override whose series has no merged master component, because neither
replica holds the master or because the master key was tombstoned, is not
matched at all. It is rejected with the reason `missing-master`, recorded with
its resolved recurrence identifier, and excluded from the schedule. The
components of a shadowed UID are neither expanded nor rejected.

Because the merge key holds the raw `RECURRENCE-ID` value, two merged override
components of one series can resolve to the same original instant, for example
when one replica writes the identifier as a local wall clock value and the
other writes it as a UTC instant. Of the overrides that resolve to one original
instant, the one with the highest `SEQUENCE` is applied; when that highest
`SEQUENCE` is shared, the one whose raw `RECURRENCE-ID` value sorts last,
comparing the two strings character by character, is applied. Every other one
is rejected, is recorded with the reason `superseded-recurrence-id`, is
excluded from the schedule and contributes no displacement.

A matched override replaces the occurrence at that original instant. The
occurrence keeps the original instant in its identifier and takes its start,
its duration source, its office, its summary, its series class and its required
attendee references from the override component, each falling back to the
master component when the override carries none: an override without
`X-OFFICE`, `SUMMARY` or `X-SERIES-CLASS` shows the master's, and an override
that names no required participant shows the master's references. An
occurrence that no override supplies shows the master's office, summary, class
and references.

A matched override whose `STATUS` is `CANCELLED` cancels the occurrence it
matches instead: the occurrence disappears from the schedule, the override is
still listed among the applied overrides with its delta, and it contributes no
displacement even when its `RECURRENCE-ID` carries `RANGE=THISANDFUTURE`.

An override whose `RECURRENCE-ID` carries the parameter `RANGE=THISANDFUTURE`
also displaces every later occurrence of the series. The displacement is

    delta = override start instant minus recurrence identifier instant

and it applies to every occurrence whose original instant is strictly greater
than the recurrence identifier instant and which is not itself the target of an
override. When a series carries more than one such override, the displacements
compose: the shift applied to an occurrence is the sum of the deltas of every
`THISANDFUTURE` override whose recurrence identifier instant is strictly earlier
than that original instant, accumulated in ascending recurrence identifier
order. Deltas and shifts are carried in seconds and the shifted start is the
original instant plus the shift in seconds. The audit reports each delta as
`delta_minutes` and each shift as `applied_shift_minutes`, in both cases the
second count divided by sixty and rounded down toward negative infinity, so
minus ninety seconds is reported as minus two. The shift ledger lists every
occurrence whose shift in seconds is not zero.

