# Stage r09: Compensating event targets

A compensating event carries no quantity and no programme of its own. It
names the event it reverses through `compensation_links.csv`. A link row
is in force at or below the frozen register revision, and among in force
rows for one compensation identifier the greatest revision governs.

A compensating event with no in force link, or whose in force link is
not `registered`, carries `CMP-WITHDRAWN`. A compensating event whose
named target is not an identifier in the canonical history carries
`CMP-NOTARGET`.

The named target is resolved against the whole canonical history. It may
stand anywhere, including behind the restored checkpoint. Its position
relative to the replay window is not a reason to reject it, and the
target is never replayed in order to reverse it: its station,
programme, kind, class and normalised quantity are read straight off the
canonical record.
