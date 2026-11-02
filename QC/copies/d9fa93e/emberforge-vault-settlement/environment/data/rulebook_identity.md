# Rulebook: Smith identity

Applies to the Emberforge crafting season. Ledger entries name the handle a
smith was using when the entry was filed. Handles are not stable across a
season. This rulebook states how a handle resolves to the canonical smith that
the season reports on.

## I1. Identity events

The identity event log records four kinds of event, each with the day it takes
effect:

* **register** - a handle enters the roster as a smith in its own right.
* **rename** - the smith previously known by one handle is known by another
  from that day forward.
* **merge** - two handles are shown to have been the same person; the absorbed
  handle is the same smith as the surviving handle from that day forward.
* **retire** - the smith leaves the roster from that day forward.

## I2. Canonical identity

The canonical identity of a handle on a given day is obtained by applying the
rename and merge events that take effect on or before that day, following each
result in turn, until no further rename or merge applies to it. The result is
the canonical smith for that handle on that day.

A handle that no event has ever renamed or merged is its own canonical
identity.

## I3. Time dependence

Canonical identity is a function of the day as well as the handle. A handle
filed before a rename or a merge takes effect resolves to whatever it resolved
to on that earlier day, and a handle filed after resolves to the later result.

## I4. Retirement

A canonical identity is retired from the effective day of its retire event
onward, and not before. Retirement attaches to the canonical identity, not to
the handle: once an absorbed handle has merged into a surviving handle, a
retire event against the surviving handle retires entries filed under either.

## I5. Reporting

The season reports on canonical identities, never on handles. Every canonical
identity that appears on any entry filed against a participating workshop is
reported by that workshop, whether or not any of its entries were settled.

## I6. Reinstatement

A register event for a canonical identity that takes effect after that
identity's retire event reinstates the identity from the register day forward.
No identity in this season is reinstated.
