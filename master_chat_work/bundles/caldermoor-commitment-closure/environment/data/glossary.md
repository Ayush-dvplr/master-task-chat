# Glossary

The terms every other document in this directory uses, and the closed lists.

**Accepted row** A feed row carrying none of the nine reason codes.

**Admitted commitment** A commitment key named by at least one accepted
commitment assertion.

**Assertion** One row of a `commitments_*` feed. Several may name one
commitment key and one of them wins.

**Blocking edge** A live edge whose blocker holds.

**Canonical handle** A `canonical_handle` appearing on a roster line.

**Clamped effort** The effort of an assertion after the floor and ceiling of
protocol section 5 have been applied to that single assertion.

**Commitment day** The calendar date of an instant after two hundred and forty
minutes have been subtracted from it.

**Discharge** A `SETTLED` commitment naming a cadence, falling due inside one of
that cadence's periods.

**Elapsed period** A cadence period whose start instant lies before the window
end.

**Envelope** The minutes a principal holds for one settlement month.

**Fold** The six step comparison normalization in the identity register.

**Governing class** The source class of the last state row applied to a
commitment.

**Holding** A commitment whose resolved state is `OPEN` or `DEFERRED`.

**Hop count** The number of alias assertions on the path that resolved a
reference.

**Live edge** An accepted edge row that is not dropped.

**Open classes** `ACTIONABLE`, `BLOCKED` and `DEFERRED` taken together.

**Principal** A person, named by an `actor_id`.

**Resolving instant** The instant a rule names for resolving a reference. It is
`observed_at` for the obligor of a commitment assertion, `due_at` for its
obligee, `asserted_at` for an edge row, and `anchor_at` for a cadence obligor.

**Settlement month** The year and month of a commitment day.

**Surface** A string naming a principal before it is resolved.

**Terminal blocker** A commitment in a closure that no blocking edge leaves.

**Wait** The wait of a commitment that is not blocked is zero, and the wait of
a blocked commitment is one more than the greatest wait among the blockers of
the blocking edges leaving it.

**Window** The half open interval from `2032-03-01T00:00Z` to
`2032-12-01T00:00Z`.

**Winning assertion** The assertion the precedence charter selects for a
commitment key.

## Closed lists

These are complete. Nothing outside them is valid anywhere in the closure.

```
commitment classes   ACTIONABLE BLOCKED DEFERRED SETTLED UNRESOLVABLE WITHDRAWN
states               OPEN SETTLED DEFERRED WITHDRAWN
reason codes         MALFORMED_ROW FEED_RETIRED OUT_OF_WINDOW
                     UNKNOWN_PRINCIPAL AMBIGUOUS_IDENTITY UNKNOWN_PROJECT
                     NONPOSITIVE_EFFORT UNKNOWN_COMMITMENT ILLEGAL_TRANSITION
unresolvable reasons CIRCULAR_DEPENDENCY AMBIGUOUS_COUNTERPARTY
edge drop reasons    EDGE_SELF EDGE_DANGLING EDGE_OUT_OF_SCOPE
effort origins       STATED DEFAULTED DECLARED_ZERO
obligee statuses     RESOLVED AMBIGUOUS UNKNOWN
budget sources       OVERRIDE REGISTERED ABSENT
waiver effects       SUPPRESSED INERT LAPSED
source classes       vault desk bridge partner mirror import relay legacy
effort units         minutes hours halfdays
record kinds         commitment state edge
identities           I1_row_partition I2_class_partition I3_actor_effort
                     I4_project_effort I5_closure_frontier
```
