# Caldermoor commitment protocol

This protocol governs every figure in the closure. Where another document in
this directory carries a rule, this file names it and that document is
authoritative for that rule. Nothing outside this directory governs anything.

## 1. Window and instants

Every instant is written `YYYY-MM-DDThh:mmZ` and is UTC. An instant in any
other shape is not an instant.

The settlement window is the half open interval

```
[2032-03-01T00:00Z, 2032-12-01T00:00Z)
```

Half open means the start instant is inside the window and the end instant is
outside it. Every interval in every document in this directory is half open on
the same reading.

## 2. Commitment day

The commitment day of an instant is the calendar date of that instant after
subtracting two hundred and forty minutes. An obligation falling due at
`2032-05-05T03:15Z` therefore has commitment day `2032-05-04`, and one falling
due at `2032-05-05T04:00Z` has commitment day `2032-05-05`.

The commitment day is the only date any deliverable carries. The year and month
of the commitment day is the settlement month, and the settlement month is what
the attention envelope in section 9 is drawn against.

## 3. Principals

A principal reference is resolved by `identity-register.md`. Resolution takes a
surface string and an instant, and returns exactly one canonical handle, or the
outcome `UNKNOWN_PRINCIPAL`, or the outcome `AMBIGUOUS_IDENTITY`. The instant a
reference is resolved at is stated by the rule that uses it and is never assumed.

For a commitment assertion the resolving instant of the `obligor` is that
row's `observed_at`. The resolving instant of the `obligee` is that row's
`due_at`, because an obligation is owed to whoever stands behind the surface on
the day it falls due rather than on the day the row was filed. The two instants
are different and neither stands in for the other.

## 4. Projects

A project reference is resolved by walking the rename lineage in
`project_events.tsv`. Only a `RENAME` event whose `effective_at` is at or
before the resolving instant applies, and the walk continues while another
applicable rename names the code reached. A reference resolved before its
rename takes effect therefore keeps the earlier code. A code the registry never
declares is `UNKNOWN_PROJECT`. For a commitment assertion the resolving instant
of `project_ref` is that row's `observed_at`.

The root of a project is reached by following `parent_code` in
`project_registry.csv` until a project with an empty parent is found. Every
rollup at project granularity is stated at the root.

Where `project_registry.csv` carries several revisions of one project, the
revision that governs an assertion is the one with the greatest `revised_at`
at or before that assertion's `observed_at`.

## 5. Effort

The effort of an assertion is an integer count of minutes and is derived from
the `effort` field of the row, which is empty, or the literal `null`, or an
integer. These three are three different things.

An empty `effort` means the obligation inherits the `default_effort` of the
governing project registry revision from section 4.

The literal `null` means the obligation carries no effort, its effort is zero
minutes, and it takes no share of any attention envelope while remaining in
every count and in every class.

An integer that is zero or below is `NONPOSITIVE_EFFORT`.

An integer above zero is multiplied by the unit factor for that row. Layouts
carrying an `effort_unit` field take the factor from it, where `minutes` is one,
`hours` is sixty and `halfdays` is two hundred and forty. Layouts carrying no
`effort_unit` field take the factor stated for that layout in
`record-layouts.md`. A unit outside the three named is `MALFORMED_ROW`, and the
three named units are the three strings written here, so a unit differing from
one of them in case alone is outside them and the row carrying it is malformed.
A layout carrying no `effort_unit` field never reads one, so no spelling can
make one of its rows malformed this way. The unit is read only for an integer
above zero, so an integer of zero or below is `NONPOSITIVE_EFFORT` whatever
unit it carries, while an `effort` that is not an integer, or an integer above
zero carrying a unit outside the three named, makes the row `MALFORMED_ROW`,
and section 6 tests that ahead of every later reason code.

Effort is then clamped into `[15, 480]` minutes, once, on the single assertion,
before it reaches any sum. An effort of zero minutes is left at zero and is not
raised to the floor.

## 6. Rejection

A row is tested against the reason codes in this order and carries the first
one that applies, never a later one:

```
MALFORMED_ROW
FEED_RETIRED
OUT_OF_WINDOW
UNKNOWN_PRINCIPAL
AMBIGUOUS_IDENTITY
UNKNOWN_PROJECT
NONPOSITIVE_EFFORT
UNKNOWN_COMMITMENT
ILLEGAL_TRANSITION
```

These nine are the only reason codes. A row that carries none of them is
accepted.

The order above is absolute and holds however the codes are discovered. Every
condition that makes a row `MALFORMED_ROW`, wherever in this directory that
condition is written down, is tested before the feed is asked whether it had
retired and before the instant is compared against the window. A row that is
malformed and late carries `MALFORMED_ROW`.

`FEED_RETIRED` applies to a row whose resolving instant is at or after the
`retired_at` of its own feed file, taken from the highest `revision` of that
file in `feed_manifest.csv`. A feed carrying a retirement instant still
contributes every row observed before it.

`OUT_OF_WINDOW` applies to a commitment assertion whose `due_at` lies outside
the window, and to a state or edge row whose own instant lies outside it.

`UNKNOWN_COMMITMENT` applies to a state row naming a commitment key that no
accepted assertion creates.

A principal reference that fails to resolve rejects the row only when it is the
`obligor`. An `obligee` that fails to resolve leaves the row accepted, and
section 8 states what an ambiguous obligee does to the commitment.

## 7. From assertions to commitments

Several assertions may name one commitment key. The winner is chosen by
`precedence-charter.md`, and the winning assertion alone supplies every field
of the commitment. A commitment key with at least one accepted assertion is
admitted. A key with none is not a commitment.

The resolved state of a commitment is computed by `precedence-charter.md` from
the state rows naming it.

## 8. Commitment class

Every admitted commitment carries exactly one class drawn from

```
ACTIONABLE  BLOCKED  DEFERRED  SETTLED  UNRESOLVABLE  WITHDRAWN
```

The class is decided by taking the first of these that holds, and the order is
part of the rule:

```
resolved state SETTLED                          -> SETTLED
resolved state WITHDRAWN                        -> WITHDRAWN
member of a live dependency cycle               -> UNRESOLVABLE
winning assertion obligee AMBIGUOUS_IDENTITY    -> UNRESOLVABLE
blocked under dependency-semantics.md           -> BLOCKED
resolved state DEFERRED                         -> DEFERRED
otherwise                                       -> ACTIONABLE
```

An `UNRESOLVABLE` commitment carries the reason `CIRCULAR_DEPENDENCY` when it
reached that class through a cycle and `AMBIGUOUS_COUNTERPARTY` when it reached
it through an ambiguous obligee. These two are the only unresolvable reasons and
a commitment that reaches the class through a cycle carries the cycle reason,
because the cycle test runs first.

`ACTIONABLE`, `BLOCKED` and `DEFERRED` together are the open classes. Open
effort is the sum of the clamped effort of the commitments in those three
classes, and a `SETTLED`, `WITHDRAWN` or `UNRESOLVABLE` commitment contributes
nothing to it while remaining in every count.

## 9. Attention envelope

Each principal holds a monthly envelope of minutes. The envelope for a principal
and a settlement month is the `monthly_minutes` recorded for that pair in
`budget_overrides.psv` when one is recorded there, and otherwise the
`monthly_minutes` recorded for that pair in `attention_budget.csv`. A pair
recorded in neither holds an envelope of zero, and every share inside it is
zero.

An envelope first gives up a reserve. The reserve of a principal for a
settlement month is thirty minutes for each line of `blocked_commitments.csv`
whose commitment belongs to that principal and has its commitment day in that
month, together with fifteen minutes for each waived period of every cadence
that principal owns, as `cadence-register.md` counts them. The distributable
minutes are the envelope less the reserve, and zero when the reserve is the
larger.

Within one principal and one settlement month the distributable minutes are
distributed across that principal's open commitments carrying effort above
zero.

When the summed clamped effort is at or below the distributable minutes, each
commitment receives its own clamped effort and the rest is left undistributed.

When the summed clamped effort exceeds the distributable minutes, they are
distributed in proportion to clamped effort by largest remainder, and a tie
between two remainders is settled in favour of the lower commitment key. A
commitment whose share then falls below fifteen minutes receives zero, and the
whole of the distributable minutes is distributed again by the same rule across
only the commitments that held fifteen or more. When that leaves no commitment
standing, every share is zero.

## 10. Escalation

A commitment escalates when every one of these holds at once, and a commitment
failing any one of them does not escalate:

```
its class is ACTIONABLE or BLOCKED
its share of its principal's envelope is below its own clamped effort
the debt its principal carries, summed over every cadence whose obligor is
    that principal, is four or more
its chain depth is two or more, or its commitment day falls in 2032-11
```

The shortfall of an escalated commitment is its clamped effort less its share.
Its trigger is `DEPTH` when only the depth condition holds, `MONTH` when only
the month condition holds, and `BOTH` when both hold. Those three are the only
triggers. Which cadences a principal owns is settled by `cadence-register.md`, and the
debt of a cadence owned by nobody is carried by nobody. A commitment that is not
blocked has a chain depth of zero.

## 11. Canonical order

The ledger and every deliverable derived from it are ordered by ascending
commitment day, then by ascending principal identifier, then by **descending**
clamped effort, then by ascending commitment key. Every other deliverable states
its own order in `output-contract.md`.

## 12. Identities

The closure holds five identities and each one is reported with its residual,
where a residual of zero means the identity held.

```
I1_row_partition      accepted rows equals normalized assertions
                      plus applied state rows plus live edges plus dropped edges
I2_class_partition    admitted commitments equals the sum of the six classes
I3_actor_effort       summed open effort over principals equals ledger open effort
I4_project_effort     summed open effort over project roots equals ledger open effort
I5_closure_frontier   summed frontier counts equals the count of terminal
                      closure pairs
```

## 13. Determinism

Two runs of the delivered program over one input directory produce byte
identical output. No deliverable carries a wall clock instant, a host name, a
path from the running machine, or any value drawn from an unordered traversal.
