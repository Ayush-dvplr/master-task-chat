# S04 interval clipping

Every interval in this pipeline is half open. [a, b) contains a and does
not contain b. Two intervals that share only an endpoint do not overlap.
An interval where b equals a is legal, has zero length and carries no
capacity.

## the base interval

The base interval of a pass is [scheduled_start_s, scheduled_end_s).

When the operational event carries event_status partial, the base
interval is intersected with [actual_start_s, actual_end_s) from the
journal. When the event is nominal, the journal times are ignored and the
scheduled interval stands even if the journal reports something else.

## the eligible interval set

The eligible set of a pass is the base interval intersected with the
availability set of its aperture from S02. It is a sorted list of
disjoint half open intervals and it may have more than one member,
because a maintenance docket in the middle of a pass splits it.

## the accounting split

The eligible set is then split at the station local accounting period
boundaries from S02. Each piece belongs to exactly one settlement
period, and a pass that straddles a boundary settles in both, as two
rows of the canonical ledger sharing one contact_id.

eligible_seconds of a canonical row is the total length of that row
pieces. A pass that produces no piece in a period produces no row in
that period.

## the zero length pass

A pass whose scheduled_end_s equals its scheduled_start_s is admitted
when that instant lies inside an availability interval of its aperture,
and rejected at predicate eight when it does not. It produces one
canonical row, in the period whose window contains the instant, with
eligible_seconds zero. It contends with nothing, because a zero length
interval intersects nothing.

## normalized_contact_intervals

One row per eligible piece, ordered by contact_id, then period_id, then
segment_start_s. A canonical row with no pieces, which is the zero
length case, contributes one row whose start and end are both the pass
scheduled_start_s and whose segment_seconds is zero.
