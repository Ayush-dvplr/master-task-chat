# Keyframe interval basis reconciliation authority policy

## Authority

The keyframe interval ledger is the sole authority for the `interval_basis` value of every render track. The
generated interval snapshot, the interval index manifest, the encoder runtime state and the encode operations journal are all derived layers. A derived layer
never overrides the authority layer, and a derived layer that disagrees with the
authority layer is by definition the layer that has to change.

## Reference domain of the `interval_basis` value

Every authority record carries a `reference_domain`. The declared reference
domain of the published contract is `presentation_interval_id`. Records recorded by the migration
service may carry `decode_order_index`; such a record stores an alternate key rather than a
published value, and the published value is obtained from `decode_order_map.json` by
selecting the row whose `alt_key` equals the recorded value and whose
`lineage_anchor` equals the active lineage anchor of that render track.

A record whose `lineage_anchor` field reads `pending` has a deferred conversion.
Its active lineage anchor is decided by the lineage registry, and the registry
only advances when the pending operations held in the encode operations journal are replayed. Until
the replay happens, the currently registered active anchor stands. After a
`supersede_lineage` operation is replayed, the anchor named in `retire_anchor`
leaves the registry and the anchor recorded on the declaring record of that
render track becomes the active anchor.

## Journal operations

The encode operations journal holds one row per operation with a `status` of `applied` or `pending`.
Replaying the encode operations journal means carrying out every pending operation in ascending
`journal_seq` order. An `apply_amendment` operation carries the record it
applies. A `supersede_lineage` operation carries the anchor it retires. A
`rollback_amendment` operation carries neither; it carries a `target_position`
instead.

A `target_position` is a one based index into the surviving authority records
at the generation the replay is advancing to. The surviving set holds one
record per active render track, being the record that stands for that render track once
competing records have been settled, and it is ordered by ascending record
sequence number. Rolling back the record at that position withdraws the
amendment it carries and restores the value that render track held under the record
immediately preceding it. Positions are computed against the set the replay
produces, so the ordering recorded in an earlier snapshot generation does not
answer the question. Each operation is carried out against the state its
predecessors in the replay left behind, so a position is read against the
surviving set as it stands at the moment that operation runs.

## Derived state

The generated interval snapshot is compiled from the keyframe interval ledger. The interval index manifest indexes the compiled snapshot and
records, per render track, the source generation it indexed and the active lineage
anchor. The encoder runtime state loads published values through the index. The encode operations journal holds
operations that have been applied and operations that are still pending. The
interval reconciliation report compares the generated interval snapshot, the interval index manifest and the encoder runtime state. It never reads the keyframe interval ledger, so an
agreement verdict from that surface says only that three derived layers match
each other.

## State digest

The canonical state digest is the sum, over every active render track, of the
published value multiplied by the weighting multiplier recorded in
`track_partition_map.json`, taken modulo 100003. Retired render tracks are excluded from the sum.

The conformance fixtures publish the same sum taken over a fixed reference
cohort rather than over the full active set. The cohort is listed by name in
`interval_conformance_fixtures.json` and covers only render tracks whose published value is already settled
in the keyframe interval ledger before any pending operation is replayed. Reproducing the cohort
digest confirms that the reference domain conversion, the weighting and the
modulus have been applied correctly. It carries no information about render tracks
whose conversion is deferred, so the full canonical state digest has to be
established from the keyframe interval ledger and the replayed encode operations journal instead.

## Ordering and ties

Entries are listed in ascending render track name order. Rank is assigned by
descending weighted value, and equal weighted values are ordered by ascending
render track name. The dependency order is a topological order of the dependency
edges recorded in the interval index manifest, and whenever two render tracks are ready at the same
time the one with the lower name comes first.

## Recovery order

The supported recovery order is `correct_interval_record`, then `regenerate_interval_snapshot`, then `rebuild_interval_index`, then `restart_encoder_runtime`,
then `replay_encode_journal`, then `reconcile_interval_layers`. Running a later transition before an earlier one
leaves the derived layers pinned to a generation that the authority layer has
already moved past.

## Preservation, minimal delta, idempotency and persistence

Exactly one authority record may be rewritten to resolve a reference domain
defect. A retired render track keeps its retirement record. A render track that received a
later amendment keeps the later value. Every other render track keeps the value it
already had. A render track counts as having received a later amendment only when
the authority records hold more than one amendment for it and the amendment the
durable state settles on stands over an earlier amendment of the same render
track, so a render track whose later amendment the replay withdraws keeps the
earlier value and is not one of them. The durable state is a function of the authority records and the
maps alone, so recomputing it consults no derived or runtime layer, and
recomputing it twice produces byte identical results.
