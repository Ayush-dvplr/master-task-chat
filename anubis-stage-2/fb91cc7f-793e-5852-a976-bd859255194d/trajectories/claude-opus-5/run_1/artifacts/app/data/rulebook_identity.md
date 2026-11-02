# Rulebook: identity

The vault has been catalogued more than once, by more than one archivist, over
more than one accession. The same physical reel therefore appears in the scan
book under more than one identifier, and the lineage book is how the lab says
which identifiers are the same thing.

Nothing downstream may treat two identifiers for one reel as two reels.

## Lineage events

A lineage event names an effective cycle, a kind, a reel it acts on, the reel
it points at, and a registration offset.

An event applies to a settlement cycle when its effective cycle is at or
before the cycle being settled. An event whose effective cycle is later than
the cycle being settled has not happened yet and does not apply: the vault
looks exactly as it did before that event was recorded.

There are four kinds of event.

**alias**: the reel it acts on is a duplicate catalogue entry for the reel it
points at. The two are one reel and always were.

**merge**: the reel it acts on has been physically consolidated into the reel
it points at. The two are one reel from the effective cycle onwards.

**supersede**: the reel it acts on has been replaced by a better scan of the
same material, which is the reel it points at. Work cut against the old reel
is work against the new one.

**retire**: the reel it acts on has been withdrawn from the vault. A retire
event points at nothing and carries no offset. A retired reel supplies no
picture to anything.

## Resolution

An identifier that no applying event acts on resolves to itself. An identifier
that an applying alias, merge or supersede event acts on resolves to whatever
the reel it points at resolves to. Resolution follows the chain as far as it
goes, so an identifier may resolve through several events to a reel several
hops away.

The lineage book of a settleable cycle never sends a chain back to an
identifier it has already passed through.

An identifier that resolves to a retired reel is retired.

## Registration offset

Two catalogue entries for one reel were rarely measured from the same physical
frame. The registration offset on an event is how far the frame coordinates of
the reel the event acts on must move to line up with the frame coordinates of
the reel it points at: a coordinate on the acted-on reel plus the offset is
the same physical frame on the reel pointed at.

An offset applies to every coordinate written against the acted-on reel,
wherever it was written. Where resolution follows a chain of several events,
the coordinate moves by every offset on the chain.

A retire event carries no offset and moves nothing.

## Consequences

An identifier that resolves to another identifier is *folded*. An identifier
that resolves to itself and is not retired is *live*.

The picture a live reel can supply is the picture any identifier resolving to
it can supply, once every one of those identifiers has been moved into the
live reel's coordinates.

Two shots cut against two identifiers that resolve to the same live reel are
two shots against one reel, and they may overlap even though the coordinates
written on them differ.
