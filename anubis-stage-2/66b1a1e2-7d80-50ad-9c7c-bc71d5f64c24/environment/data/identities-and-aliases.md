# Attendee identities and handles

## The attendee register

The attendee register named by the index (role `attendees`) is tab separated
with the columns `id`, `name`, `home_office` and `title`. A registered
identifier is a value of the `id` column.

## Handles

Events do not always name people by identifier. A participant may be named by a
handle, such as an on call rota (`duty-emea`), a role (`chief-of-staff`) or a
registered identifier that is delegated to someone else for a while. The handle
table named by the index (role `aliases`) is comma separated with the columns
`handle`, `target`, `effective_from` and `status`. Each row is a link from a
handle to a target that applies from its `effective_from` date onward. Rows
whose `status` is not `active` are ignored.

## Resolving a reference

Every participant reference of an occurrence is resolved on one date: the UTC
date of the occurrence's original instant. Start at the reference itself. At
each step, among the active links from the current name whose `effective_from`
is not later than that date, take the one with the greatest `effective_from`,
the smallest target winning a tie; if there is none, stop. Otherwise follow the
link to its target. If the target is a name already visited on this walk, the
walk has entered a cycle: stop, and take as the result the smallest name
(compared as strings) among the names from the first visit of that target to
the end of the walk. A link from a name to itself is a cycle of one name.

A registered identifier is a name like any other, so a link from a registered
identifier delegates that person. The result of the walk is the resolved
attendee when it is a registered identifier, and the reference is unresolved
otherwise; an unresolved reference names nobody and is dropped.

The number of hops is the number of links followed, including the link that
closes a cycle. The outcome of a resolution is `direct` when no link was
followed, `resolved` when links were followed and the walk stopped without a
cycle, `cycle` when the walk stopped on a cycle, and `unresolved` when the
result is not a registered identifier, whatever happened on the way.

Worked example. On 2027-06-16 `chief-of-staff` has links to `duty-amer` from
2027-01-01 and to `ATT-021` and `ATT-022` from 2027-06-16. The latest date
wins and the smaller target breaks the tie, so the reference resolves to
`ATT-021` in one hop. On 2027-06-15 it follows `duty-amer`, then the
`duty-amer` link in force on that date.

## Where resolved attendees are used

The required attendee list of an occurrence is the sorted list of distinct
resolved attendees of its references. That list is what conflicts, settling,
the load fold, attendance, travel blocks, busy conflicts and the chargeback
use. The synchronisation projection of sync-and-manifest.md is the one place
that keeps references exactly as written.
