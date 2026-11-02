# Committed minimums

Sections of this document are amended by `errata_2031-07.md`.

## 1. Agreements

`commitment_agreements.csv` carries, for one agreement, a customer, a site, a
floor with its unit, a recurrence, a first cycle and an until cycle. The until
cycle is inclusive. The recurrence is `every_cycle`, which is due in every
cycle of the range, `alternate_from_first`, which is due in the first cycle of
the range and every second cycle after it, or `first_cycle_of_month`, which is
due in every odd numbered cycle of the range.

The governing floor of an agreement in a cycle is taken from its admitted rows
whose effective instant is at or before the start of that cycle, keeping the
greatest effective instant, ties broken by the greater `revision_seq`. The
figure converts at the equivalent conversion stage along the walk of the
request it covers.

An agreement covers the request whose canonical id and site match the
agreement. The node named on an agreement is descriptive and does not narrow
what it covers. Where more than one claiming request of that canonical id and
site falls in the same cycle, the obligation attaches to the request with the
earliest governing effective instant, ties broken by the ascending reported
reference, and the other requests of that identity carry no honoured minimum in
that cycle. Where an agreement is due in a cycle and no request of that
customer and site claims in that cycle, the obligation is tallied as
`floors_unmatched`.

## 2. Exceptions

`commitment_exceptions.csv` changes the obligation of one agreement in one
cycle. An exception applies when it is admitted, when no live retraction
targets it, and when it is endorsed by an approver holding the scope
`commitment` or the scope `any` at the instant of the audit entry whose `apl`
matches its `approval_ref`. An exception with `action` of `skip` drops the
obligation for its cycle. An exception with `action` of `move_to` drops it
from its cycle and adds the same obligation to `target_cycle`, whether or not
the recurrence would have made it due there. Exceptions are tallied as
`exceptions_applied`, `exceptions_unendorsed` and `exceptions_retracted`.

## 3. Honouring order

Obligations are honoured one at a time in ascending priority rank, ties broken
by ascending agreement id. The governing rank of an agreement in a cycle comes
from the admitted rows of `priority_register.csv` with the greatest effective
instant at or before the start of the cycle, ties broken by the greater
`revision_seq`.

An obligation is honoured up to the floor, never beyond what the covered
request claims, and never beyond the capacity still unused at the moment it is
honoured. An obligation honoured to its full floor is tallied as
`floors_honoured_full` and one honoured in part as `floors_honoured_short`.
The honoured amount of a request is reported as `floor_equiv`.
