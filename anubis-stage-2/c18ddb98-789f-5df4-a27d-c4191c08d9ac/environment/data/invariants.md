# Global invariants

These hold of every settled window this platform produces. They are the
properties an operator checks before signing a window off. They are stated as
properties of the result, not as steps.

## V1 Conservation

The count of records that were in the window and eligible to be settled equals
the curated count plus the withdrawn count plus the quarantined count, exactly.

The charge the window settled equals the total settled by its settled domains,
and equals the total settled by its settled channels. The curated payload units
of the window equal the total curated payload units of its settled domains.
Within each settled channel, the charges attributed to its settled member
domains total the charge that channel settled.

Every one of those identities is reported as a residual, and every residual in a
correct settlement is zero.

## V2 Referential closure

Every identifier that appears in a settled artifact refers to something that
exists. Every feed named in a domain report is a feed of that domain. Every
domain named in a channel report is a member of that channel. Every record
identifier named anywhere is a landing record of this window. Every canonical
producer named is either an entry in the producer register or the target an
identity event in force pointed at.

## V3 Uniqueness and disjointness

No record appears twice in the ledger. No record is curated in two domains. The
curated identifiers and the dropped identifiers of a domain report share no
member. The designated feeds of two different channels share no member.

## V4 Monotonicity

The running total of the ledger never decreases as the ledger is walked in its
own order, and the last row of the ledger carries the charge the window settled.

## V5 Canonical order

Every list of identifiers in a settled artifact is in ascending order compared as
text. Every array of rows is ordered by the identifier that names the row, except
the ledger, which has its own order and carries an explicit sequence.

## V6 Determinism and idempotence

Settling the same working set twice produces byte identical artifacts. Nothing
in a settled window depends on the order files were read, on a clock, on a random
draw, or on anything outside the working set.

## V7 Confluence of the quarantine state

There is exactly one state in which the quarantine rules all hold at once, and it
does not depend on the order feeds were considered in.

## V8 Cap and floor

No settled domain curates more payload units than its cap allows. Every feed with
at least one record eligible for curation in a settled domain has at least one
curated record in that domain. No curated record settles at a unit rate below the
floor of its feed.

## V9 Grid

Every unit rate the platform places is a whole multiple of the settlement grid
spacing, and every charge is a whole number of micros. The one unit rate that is
not placed is a feed floor: where the floor of a feed is the last word on a
record, as the costing rulebook has it, the record settles at that floor exactly
as the feed register carries it, whether or not the floor sits on the grid. No
settled figure is ever fractional and no settled figure is ever recorded as
text.

## V10 Scope

A domain report exists exactly when the domain curated at least one record. A
channel report exists exactly when at least one of its member domains did. There
is no report for anything else, and nothing that should have a report is missing
one.

## V11 Recoverability

The window summary states the platform properties that were not written down: the
sequence in which the adjustments compose, the micros per basis point of the
backpressure surcharge, the spacing of the settlement grid, the convention used
for values falling between grid points, and the reading of the tombstone rule.
Exactly one combination of those five reproduces every published control figure
of the calibration slice, and that same combination settles this window.
