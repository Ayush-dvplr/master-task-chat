# Merge ladder

The merge runs over the local replica as decoded and the server replica as it
stands after the outbox replay of outbox-replay.md. The change log it consults
is the union of the two journal shards read as journals.md describes.

A calendar object is keyed by the triple of collection id, UID and the raw
`RECURRENCE-ID` value, where a master component carries the empty string. Each
key may appear in the local replica, in the server replica or in both.

A key present in one replica only is accepted as it stands and the decision rule
is `sole-replica`.

A key present in both replicas is contested and the winner is chosen by the
ladder named by `conflict_policy`.

When `conflict_policy` is `sequence-major` the ladder is: the higher `SEQUENCE`
wins; otherwise the replica with the higher revision number for that key in the
change log wins; otherwise the `authority_replica` wins. `LAST-MODIFIED` is
excluded from this ladder because the server clock runs ahead of the local
clock.

When `conflict_policy` is `mtime-major` the ladder is: the later modification
time wins, comparing the two values exactly as written with no clock
correction; otherwise the replica with the higher revision number for
that key in the change log wins; otherwise the `authority_replica` wins. This
was the v3 ladder and it is retained for stores that predate the clock audit.
The modification time of a component is its `LAST-MODIFIED` value, or its
`DTSTAMP` value when it carries no `LAST-MODIFIED`. A component that carries
neither is older than any component that carries one, so the other replica wins
at this step; when neither component carries either, this step decides nothing.

The revision number for a key and a replica is the largest `revision` value
among change log records whose `collection`, `replica`, `uid` and
`recurrence_id` all match and whose `op` is not `delete`. A key with no such
record has revision minus one. A component that carries no `SEQUENCE` has
sequence zero wherever a sequence is compared or reported.

The change log also records deletions. A record whose `op` is `delete` says
that its replica removed the calendar object of that key. A key present in one
replica only is tombstoned when the change log holds a `delete` record for the
same collection, UID and recurrence identifier from the other replica whose
`revision` is greater than the revision number of the holding replica for that
key. A tombstoned key is dropped from the merge: it has no merged component, it
is not expanded and it holds nothing for the duplicate test below. Its decision
is still recorded, with the deleting replica as the winner and the holding
replica as the loser. Delete records take no other part in the merge; in
particular they never count toward a revision number, so a delete record on a
contested key changes nothing.

The decision rule recorded for a contested key is `sequence` when the sequence
step decided it, `last-modified` when the modification time step decided it,
`revision` when the change log step decided it, and `authority` when the
authority replica step decided it. The decision rule of a tombstoned key is
`tombstone`.

When the same UID is held by more than one collection after the merge, the
collection that appears earliest in the `collections` array is the primary
holder. Components of that UID in later collections are shadows. Shadows are
recorded, are excluded from expansion, and still appear in the synchronisation
state because they exist on the server. A collection whose every key for a UID
was tombstoned does not hold that UID.

