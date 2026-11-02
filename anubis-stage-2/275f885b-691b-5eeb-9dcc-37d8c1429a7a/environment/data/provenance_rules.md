# Provenance rules

## Head count candidates

Three sources offer a head count for a claim. The field intake offers the `head_count` of the
surviving requisition row, and an empty field offers nothing. The dispatch stream offers the
head count of the record in view with the highest `version` for the block and round, where a
record carrying `op` of `delete` at the highest version offers nothing and a record carrying
`op` of `delete` below the highest version decides nothing. Where more than one record in view
shares the highest `version` for one block and round, or more than one named round is in play,
the record with the later `recorded_at` offers the value. The registry offers the
last head on hand in view for the block, read under the field conventions of
`corpus_index.md`.

`source_declarations.properties` declares the date of the recording system cutover. One source
governs head counts for rounds whose window opens before that date and one source governs head
counts for rounds whose window opens on or after it. The register does not record which source
governs on which side of the cutover. `governance_observations.log` records the source the
settlement desk treated as governing for sampled claims, written as `governed_by=`, and that
evidence settles the question for the whole campaign. The registry never governs while another
candidate offers a value, and it supplies the head count only when no other candidate does.

A claim with no candidate head count is rejected.

## Amendment notices

An amendment notice adjusts one target quantity for one block and round. The target
`head_count` adjusts the governing head count before any factor is applied. The target
`handling_ceiling` adjusts the handling ceiling for that block and round. An adjustment written
in parentheses reduces the quantity by the amount in the parentheses.

A notice is authorised when the role in `signed_by` carries `can_amend` in
`authority_scopes.json` and the block region lies inside the scope of that role. An unauthorised
notice is counted and decides nothing.

An authorised notice is timely when its `recorded_at` falls strictly after the moment the
quantity it adjusts was recorded and strictly before the close of the claim window. The moment a
governing head count was recorded is the `recorded_at` of the record that offered it, and where
the registry offered it that moment is the start of the calendar day in depot local time on
which the claim window of the round of settlement opens. The moment a handling ceiling was
recorded is the `issued_at` of the ceiling row in force. A notice
that is authorised and not timely is counted as stale and decides nothing.

Authorised and timely notices apply in `recorded_at` order with `notice_ref` breaking a tie.
An adjusted quantity never falls below zero.

Authority is tested before timeliness, and a notice counts under one code only.

## Laboratory assays

`potency_assays_h1.txt` records the measured doses per unit of a lot. Where an assay exists for
a lot identity it governs the dose content of that lot and the reference table decides nothing
for it.
