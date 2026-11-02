# Precedence policy

Three source layers describe the same grants. A layer supplies a field group
only when its governing record carries values for that group. The field groups
are `identity` for holder reference, zone and parent, `time` for the effective
bounds, and `frequency` for the frequency bounds. Each group is settled
independently: the governing value for a group comes from the highest ranked
layer that supplies that group for that grant.

| rank | layer |
| --- | --- |
| 1 | coord |
| 2 | core |
| 3 | office |

One documented exception promotes a single layer to rank one for exactly one
licence segment and exactly one field group, and leaves the remaining ranks in
their published order. The register does not restate the exception here. It
records, in `precedence_observations.csv`, the layer the published register
actually followed for a sample of grants and field groups, and the exception
triple of segment, field group and promoted layer follows from that sample.
The exception never touches the `identity` group, so holder resolution and the
licence segment are always settled by the published ranks.

The governing record of a grant, as opposed to the governing record of a layer,
is the governing record of the highest ranked layer that supplies the grant
`identity` group. Its action decides whether the grant is withdrawn.

Within one layer a grant may carry several records. The governing record of a
layer is the visible record with the highest revision. When two visible records
share the highest revision the register applies one tiebreak on `recorded_at`,
the same tiebreak everywhere, and `register_governing_flags.csv` records which
of the tied records the published register treated as governing.

Holder registry conflicts are settled in this order.

| step | rule |
| --- | --- |
| 1 | the registry row with the latest as_of wins |
| 2 | on a tie the row whose zone_of_record equals the grant zone wins |
| 3 | on a tie the row whose zone_of_record sorts first wins |

The `status_snapshot` column of a registry row is a convenience copy and binds
nothing. `holder_status_history.csv` is the authority for holder status, read at
the effective start of the grant under test, taking the row with the latest
`status_from` at or before that instant, and on a shared instant the status
that sorts last. A holder with no such row counts as `provisional`.
