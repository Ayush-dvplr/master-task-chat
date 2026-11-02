# Global invariants and closure

These hold over the whole incident window at once. A result in which every part
is locally defensible but one of these fails is a wrong result.

## Counted and set aside

Every event the journal carries is either counted in the window's figures or
set aside. There are five reasons an event is set aside, and an event is
tallied once under every reason that applies to it, so the reason tallies can
sum to more than the number of events set aside.

The five reasons are `outside_window`, `retired_worker`, `unprobed_slot`,
`unreported_park` and `unresolved_worker`. An unresolved or retired worker is
established before anything else can be read about the event, so no further
reason is tallied for it.

## Byte conservation

The reporter writes one park record of twenty four bytes for every spin sample
an event took, so the bytes a counted event emitted is twenty four times its
spin count. The park export records the bytes that actually reached the log for
that event. The window's residual is the emitted total less the logged total
over the counted events, and it is never assumed to be zero: the residual is
the measurement of what the log dropped.

## Referential closure

Every counted event has a canonical worker and an authoritative slot that
together name exactly one row of the probe export and exactly one report of the
park export. Every park report names a host the cell table carries and a tenant
class the tenant table carries. An event that fails either of the first two
conditions is set aside; the last two conditions hold over the shipped
material and are not a way to set an event aside.

## Uniqueness

A canonical worker and slot pair names at most one probe row and at most one
park report. A lock class carries at most one budget per rung. A registry tag
carries at most one row per revision number.

## Ordering

The counted events of the window stand in one order: by segment identifier
first, then by authoritative slot. A figure that reads the first counted event
of a worker, such as the pool that worker's row reports, reads that order.

## Partition agreement

The counted events of the service cell reports partition the counted events of
the window: every counted event appears in exactly one cell report, and the
counts add up. The same holds for the tenant segment reports. A cell or a
segment that no counted event reaches still reports, and reports zero.

## How the reports are written

Every report the window produces is written as text in exactly the style of the
one worked example report that ships with this material, and in no other style.
The example is the whole statement of that style. Nothing else in this material
describes it.
