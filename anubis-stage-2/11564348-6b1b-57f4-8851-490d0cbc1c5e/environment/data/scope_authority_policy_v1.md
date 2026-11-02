# SUPERSEDED first edition of the reminder surface authority policy

This edition is superseded by scope_authority_policy.md and binds nothing. It
is kept for audit only.


## Scope

This policy governs the reminder surface of the release train. It is binding on
every layer that claims to describe the surface, and on every account of a
surface incident.

## Authority

The change ledger `scope_change_ledger.jsonl` is the only authority for the
reminder surface. Every other file that names a scope, a value, a digest or a
household version is a derived layer. A derived layer is evidence about the
past, never a source of truth about the present.

## Replay order

The authority replay walks the ledger ordered by effective generation
ascending, and by record sequence ascending inside a single effective
generation. This composite ordering key is written `effective_generation,seq`
whenever an account has to name it. Record sequence alone is a different
ordering key, written `seq`, and it is the ordering key of the control replay
defined below. The two orderings select a different record as the final state
of a scope whenever a lower generation was recorded after a higher one.

## Record semantics

Each ledger record carries a record sequence, a scope, an operation, a value,
a urgency class, an authority rank, a reference domain, a lineage anchor, an
effective generation and a recorder. The operations are as follows.

A `publish` record admits a scope to the active surface with its value. A
publish that names a scope already active, or already retired, changes
nothing.

A `revise` record replaces the value of an active scope. A revise that names
a scope which is not active changes nothing.

A `deprecate` record opens a deprecation on an active scope and records the
authority rank and the effective generation of that deprecation. Deprecations
stack, so a scope may carry more than one open deprecation.

A `restore` record closes the most recent open deprecation of its scope when
the authority rank of the restore is greater than or equal to the authority
rank of that deprecation. When the authority rank of the restore is lower, the
restore changes nothing and the deprecation stays open.

A `withdraw` record removes a scope from the active surface, appends it to
the retired list, and discards every open deprecation on it. A withdrawn
scope never returns.

A record that changes nothing is inert. Inert records are still parsed, still
counted in the ledger, and are excluded from the effective record set.

## Reference domains

A record whose reference domain is `scope_id` carries its value
literally. A record whose reference domain is `restricted_scope_index`
carries an alternate key rather than a value, and the value must be resolved
through `restricted_scope_map.json` by matching both the alternate key and
the lineage anchor. Alternate keys repeat across rows, so the lineage anchor
is what settles the row.

A record whose lineage anchor is `pending` has no anchor of its own yet. The
release operations journal carries a `supersede_anchor` operation for that
scope which names the retired anchor and the surviving anchor. The surviving
anchor is the anchor that resolves the record.

## Journal replay

`coverage_operations_journal.jsonl` carries operations that the builder runtime
has not yet folded into the authority state. An operation whose status is
`applied` is already reflected in the ledger. An operation whose status is
`pending` must be replayed. An operation whose status is `rejected` was
refused by the release desk and must not be replayed.

An `apply_change` operation admits the ledger record it names into the
effective record set. A ledger record that an `apply_change` operation names
with status `pending` is inert until that operation is replayed. A
`supersede_anchor` operation settles a pending lineage anchor. A
`rollback_change` operation withdraws the ledger record it names from the
effective record set.

## Deprecation window

`urgency_class_catalogue.json` publishes the deprecation window in
generations. A scope that still carries an open deprecation once the replay
has finished leaves the active surface and joins the retired list when the
difference between the surface generation and the generation of that open
deprecation is greater than or equal to the window. A scope whose open
deprecation is younger than the window stays active.

## Surface generation

The surface generation is the largest effective generation recorded on any
ledger record, whether or not that record turned out to be effective.

## Release version fold

The household version starts at `0.0.0` and folds one step for every effective
record, taken in authority replay order. A `breaking` class increments the
major component and resets the minor and patch components to zero. An
`additive` class increments the minor component and resets the patch component
to zero. An `internal` class increments the patch component. Inert records do
not fold. The version is reported as three integers joined by dots.

## Surface digest

The surface digest is the sixteen character hexadecimal digest produced by
BLAKE2b with an eight byte digest size over the UTF-8 encoding of the compact
JSON serialization of the active surface, where the serialization sorts keys
and uses no whitespace after the separators. `scope_conformance_fixtures.json`
carries a worked digest over a two scope surface so that an implementation can
be checked before it is trusted.

## Control replay

The control replay rebuilds the whole surface a second time from the ledger
alone, ordered by record sequence ascending, with no journal replay. It
produces a control digest under the same digest rule. The control replay is a
diagnostic and never a source of truth. Reporting one digest in both the
surface digest field and the control digest field is a reporting fault.

## Rank total order

The rank total order sorts the active scopes by value descending and by
scope name ascending where two scopes carry the same value.

## Transitions

A transition identifier is the record sequence, the scope and the operation
of an effective record, joined by colons, with the literal prefix `seq`. The
transition list is the identifiers of every effective record in authority
replay order.

## Candidate causes

`urgency_class_catalogue.json` publishes a closed set of candidate causes.
Exactly one candidate cause is supported by the evidence. An account must also
name the one candidate cause that the control replay falsifies, together with
the falsifier `control_replay_digest_matches_snapshot` when the control digest
reproduces the digest stamped on the generated snapshot.

## Preservation

The ledger, the journal, the restricted scope map, the catalogue and every
other file under the evidence directory are read only. A recovery that edits
them is void. Retired scopes are preserved in the retired list in the order
in which they were retired.

## Serialization

Every JSON artifact is written as UTF-8 with two space indentation, line feed
line endings and a trailing newline. Integers are written as integers. No
floating point value appears in any artifact.

## Determinism

Running the recovery twice produces byte identical artifacts. Deleting the
derived layers and running the recovery again rebuilds them from the ledger
alone.
