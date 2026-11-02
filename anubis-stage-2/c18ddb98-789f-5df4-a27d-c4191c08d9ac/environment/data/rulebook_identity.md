# Rulebook: identity

Filed under I in the platform reference set. Producers are the entities whose
change records land on feeds. Upstream systems rename them, merge them and
retire them, and the landing records keep whatever reference the upstream system
happened to be using at the moment of emission. This rulebook says what a
reference means. It does not say when identity is resolved relative to any other
piece of settlement work.

## I1 The producer register is the roll of live identifiers

The producer register lists every identifier the platform recognises as a
producer in its own right. A reference that is not in that register is not a
recognised producer unless an identity event maps it onto one.

## I2 Identity events carry an effective instant

Every identity event carries an effective instant, a subject reference and a
target reference. An event is in force for a landing record when the event
effective instant is at or before the emission instant of that record. An event
whose effective instant is after the emission instant of a record has not
happened yet as far as that record is concerned, and it must be ignored for that
record. Two records emitted an hour apart can therefore resolve the same
reference to two different canonical producers, and that is the intended
behaviour rather than an inconsistency.

Identity events are not confined to the window. An event effective long before
the window opened is in force for every record in the window. An event effective
after the window closed is in force for none of them.

## I3 Rename

A rename event says the subject reference is now written as the target
reference. Once a rename is in force, the subject reference is no longer a
canonical identity: it stands for the target.

A reference can be renamed more than once over its life. Where several rename
events with the same subject reference are in force for one record, the one with
the latest effective instant is the one that speaks; if two of them share that
latest instant, the one with the greatest event identifier read as text speaks.
Earlier renames of the same subject are superseded and have nothing further to
say about that record.

## I4 Merge

A merge event says the subject reference has been absorbed into the target
reference. Once a merge is in force, records that arrived under the subject
reference are treated as records of the target producer. A merge behaves exactly
like a rename for the purpose of naming the canonical producer, and the same
supersession rule applies to repeated merges of one subject.

Merging is consequential rather than cosmetic. Records that arrived under
different references but resolve to the same canonical producer are records of
one producer everywhere downstream: in the producer list of a domain report, in
the entity set a tombstone reaches, and in the pool that a defect measurement
walks.

## I5 Chains

Renames and merges compose. If a reference resolves to a second reference, and
an event in force resolves that second reference onward to a third, then the
original reference resolves to the third. Following the chain continues until a
reference is reached that no event in force renames or merges away. That final
reference is the canonical producer for the record.

## I6 Retirement

A retire event says the subject reference has been retired from service. A
record whose canonical producer is retired as at its emission instant is
withdrawn from the curated output and booked with the reason
`withdrawn_retired_producer`. A record emitted before the retirement took effect
is unaffected by it.

Retirement applies to the canonical producer the chain arrives at, not only to
the reference written on the record.

## I7 Unrecognised references

A reference that resolves to something the producer register does not list is
unrecognised. Its records are withdrawn from the curated output and booked with
the reason `withdrawn_unknown_producer`.

## I8 Cyclic references

Upstream systems occasionally file identity events that point at each other, so
that following the chain never reaches a reference that stays put. A record
whose reference sits in such a chain has no canonical producer. It is withdrawn
from the curated output and booked with the reason `withdrawn_cyclic_identity`.

The audit artifact reports, for every distinct reference seen on a landing
record in the window, how it resolved: the canonical producer it resolved to,
the outcome of that resolution, and how many records carried it. Because a
reference can resolve to different canonical producers at different instants,
as I2 sets out, a reference that resolved more than one way is reported once for
each distinct outcome it took, and the count on each is the records that carried
the reference under that outcome. An unknown or a cyclic outcome has no
canonical producer, so a row for such an outcome reports an empty canonical
producer.
