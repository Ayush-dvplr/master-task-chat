# Data quality rules

## Rejects

A requisition row that fails admission is rejected and counted under exactly one code. The
codes apply in this order and the first that holds decides: `RC_UNKNOWN_BLOCK` when the holding
key resolves to no master block or the round code names no round, `RC_WINDOW` when
`effective_at` falls outside the claim window, `RC_LATE_RECORD` when `recorded_at` falls at or
after the close of the claim window, `RC_WITHDRAWN_BLOCK` when the master version in force
carries a withdrawal at or before the window opening, `RC_EVENT_CONFLICT` when two visit events
share an event identifier and differ in any other field for that block and round,
`RC_EPOCH_GAP` when a restock event falls inside the claim window, and `RC_NO_HEADCOUNT` when no
source offers a head count.

Where two visit events share an event identifier and differ in any other field, neither row
registers an event anywhere in the settlement.

Rejected rows carry no claim and enter no ledger. A rejected row still counts in the source row
totals.

## Counted conditions

The counted codes record work the settlement did without rejecting a claim.
`RC_DUPLICATE_COLLAPSED` counts requisition rows collapsed inside the span.
`RC_STALE_REVISION` counts requisition rows recorded after the span closed.
`RC_AMENDMENT_STALE` and `RC_AMENDMENT_UNAUTHORISED` count amendment notices that decided
nothing. `RC_LOT_CYCLE` counts observed lots whose certificate chain is a cycle at an opening at which
they are observed, with observation as `substitution_rules.md` defines it.
`RC_ILLEGAL_TRANSITION` counts certificates that made no move: for each observed lot, the
certificates of its chain in force that made no move at the first observed opening at which any
such certificate is in force, so a lot contributes at one opening only. `RC_NO_SUBSTITUTE`
counts lots as `substitution_rules.md` states. `RC_UNIT_UNDECLARED` counts lots with no declared measurement
basis. `RC_HEADER_GAP` counts record files whose declared row count differs from the number of
rows the file holds.

A declared row count that differs from the rows present changes no quantity. The rows present
are the rows.
