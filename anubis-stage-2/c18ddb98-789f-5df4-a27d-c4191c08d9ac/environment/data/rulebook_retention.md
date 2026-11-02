# Rulebook: retention

Filed under R in the platform reference set, near the end. Retention decides how
much of the admitted traffic the platform actually keeps. Each rule stands on
its own.

## R1 Tombstones erase the whole window for an entity

A landing record carries an operation. Most records are upserts. A record whose
operation is a tombstone announces that the upstream system has deleted the
entity.

This platform does not use the forward only delete semantics that most change
data capture pipelines use. Read this paragraph carefully, because it is the
opposite of the usual convention and the settlement depends on it. When a
tombstone for an entity is emitted anywhere inside the ingest window, every
landing record in that window whose canonical producer is that same entity is
withdrawn from the curated output, and that includes records emitted **earlier
in the window than the tombstone itself**. It is not only the records that
follow the tombstone. The window is treated as though the entity had already
been deleted when the window opened, so the curated state of that entity reverts
to whatever it held at window open and the window contributes nothing further
for it. Every one of those records, the tombstone included, is booked with the
reason `withdrawn_by_tombstone`.

A tombstone reaches records on every feed and in every domain, not only the feed
it landed on, because it speaks about an entity rather than about a stream. It
reaches records by canonical producer, so a record that arrived under a
superseded reference is reached exactly when that reference resolves to the
tombstoned entity.

A tombstone emitted outside the window says nothing about this window. A
tombstone on a record that took no part in the settlement at all says nothing
either.

A tombstone also says nothing when the record carrying it had already been
settled otherwise by the time the tombstone rule was reached. Only a record that
was still eligible for curation at that point announces a deletion: a record
that was itself withdrawn before then, because it landed on a feed of a
provisional domain, because its canonical producer was retired, because its
reference did not resolve, or because no card governed it, speaks for nothing
beyond itself. Which withdrawals precede the tombstone rule is a consequence of
the order the rules bear on a record, which the published control figures pin
down.

The audit artifact reports the canonical identifiers of the entities that a
tombstone reached in this window.

## R2 Every domain has a curated cap

A domain carries a curated cap expressed in payload units. The curated records
of a domain may not carry more payload units in total than that cap allows. When
the admitted traffic of a domain would exceed its cap, records are dropped from
the curated set until the total fits, and each dropped record is booked with the
reason `withdrawn_by_curtailment`.

Dropping is not arbitrary. Of all the ways to fit inside the cap, the platform
keeps the one that settles the most charge. Where two ways settle exactly the
same charge, the platform keeps the one that retains more records. Where two
ways settle the same charge and retain the same number of records, the platform
keeps the one whose retained record identifiers come first when the identifier
lists are compared in order as text.

The domain report names the records that were dropped this way, separately from
the records that survived.

## R3 No curated feed may be silenced by curtailment

A domain is only meaningfully settled when every feed that reached it still
speaks for itself. If a feed has at least one record that survived everything up
to curtailment, then after curtailment that feed must still have at least one
curated record in that domain. A way of fitting inside the cap that would silence
such a feed entirely is not a valid way of fitting inside the cap, however much
charge it would settle.

This obligation binds together with R2 rather than after it: among the ways of
fitting inside the cap that keep every such feed speaking, the platform picks by
the R2 preferences.

## R4 The quarantine floor is a warning, not a gate

A domain carries a quarantine floor expressed in payload units. When the curated
payload units of a domain finish at or below its quarantine floor, the domain is
flagged in the quality register as sitting at its quarantine floor. The flag is
advisory. It does not withdraw records, it does not remove the domain from the
settlement, and it does not change any charge. A window in which no domain is at
its floor reports an empty list, which is a normal outcome rather than a missing
value.
