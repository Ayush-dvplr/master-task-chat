# Worker identity and the thread registry

The thread registry is the only authority on what a worker column names. It
carries one row per recorded fact about a tag. A row gives the tag, the
canonical tag it stands for, the pool key, the first and last epoch the row
covers, the revision number of the row, and the status of the tag under that
row.

## Live rows

A row is live at an epoch when that epoch is at or after the row's first epoch
and at or before the row's last epoch. A tag with no live row at the epoch of
an event leaves that event's worker unresolved.

## Which live row governs

The registry is append only. When a worker is re homed, renamed or withdrawn,
the operator writes a new row at a higher revision number and leaves the old
row in place, so a tag can have more than one live row at the same epoch.

**When more than one row for the same tag is live at an event's epoch, the row
that governs that event is the row carrying the lowest revision number.** A
higher revision records what the operator learned or changed afterwards. It
governs later work, and it never governs an event that was already in flight
when it was written. A reading that takes the newest live row is a reading of
the wrong window.

## Following the canonical tag

When the governing row's canonical tag is the tag itself, resolution ends
there. When the canonical tag differs from the tag, the row is an alias and
resolution continues from the canonical tag, choosing a governing row again by
the same rule at the same epoch.

Resolution follows at most six rows. A resolution that would need a seventh
row, or that reaches a tag with no live row, leaves the worker unresolved, and a
chain that returns to a tag it has already followed runs out of rows the same
way. An event whose worker is unresolved
takes no part in any figure.

## Status

A tag whose governing row names the tag itself and carries a status other than
active is retired at that epoch. An event whose worker is retired takes no part
in any figure.

Alias rows carry a status of their own that describes the alias, not the worker
it resolves to, and no alias row ever retires a worker.

## Canonical identity downstream

Once an event's worker is resolved, the canonical tag is the identity that
event carries everywhere afterwards. The tag written in the worker column is
not that identity and never stands in for it. The probe export and the park
export are both keyed by the canonical tag together with the authoritative slot
of the event.
