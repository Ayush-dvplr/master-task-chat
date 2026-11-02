# P03 candidate board assembly

Produces the boards the hall recorded, as evidence to be screened later.

## Which pairing row governs a table

Group the applicable rows of `recorded_pairing_table.csv` by round and
`table_no`. A row is applicable when its `event_reference` is this event
and its `pairing_status` is in the applicable list of the
`recorded_pairing` section of `revision_precedence.toml`. Of the rows of a
group take the one with the highest `sheet_revision`, breaking a tie on the
highest `source_seq`. A `rescinded` row is out of scope whatever its
`sheet_revision` is.

## Identifiers

`player_a` and `player_b` are resolved through the identifier closure of
P01. A candidate board whose resolved identifier is not an entrant of this
event is dropped and appears in no delivered document.

A candidate board whose two resolved identifiers are equal is dropped.

## Delivered

`round_match_candidates.csv`, one row per surviving group, ascending round
then ascending `table_no`. `player_a` and `player_b` are the resolved
identifiers in the column order the governing row carries them, and
`sheet_revision` and `source_seq` are those of the governing row.
