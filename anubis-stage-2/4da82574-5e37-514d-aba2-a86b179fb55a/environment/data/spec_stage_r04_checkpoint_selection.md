# Stage r04: Checkpoint selection

`checkpoint_register.csv` lists the checkpoints and
`checkpoint_states.jsonl` holds their bodies. A checkpoint is usable for
a replay whose end boundary is E when every one of these holds: its
register row stands at a revision at or below the frozen register
revision; its status is `sealed`; a body carrying its identifier is
lodged; the digest recomputed from that body equals the digest the
register declares; every identifier in the body's applied ledger stands
at or before the body position in the canonical order; and the body
position is strictly less than E. A ledger identifier the canonical
history does not carry stands at no position and fails that test.

Among the usable checkpoints the one with the greatest position is
selected. When none is usable the replay runs from an empty state with
watermark zero.

Every rejected register row is reported with one reason:
`draft_revision`, `not_sealed`, `body_missing`, `digest_mismatch`,
`ledger_past_watermark` or `position_at_or_after_end`, tested in that
order.

`prior_epoch_archive.db` holds the counters the archive kept for some
checkpoints and the station and applied counts for each. Where the
archive and the body disagree the body governs; the difference is
reported and never applied. `allotment_ceiling_history.tsv` holds the
ceilings of earlier revisions and is read for the revision the selected
register row carries.
