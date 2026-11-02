# P01 entry normalisation

Produces one settled entrant record per player of this event.

## Which rows are in scope

A row of any register governs only when its `event_reference` equals the
`event_reference` of `division_topology.xml`. Every other row governs
nothing, whatever else it carries.

## The identifier closure

`entry_alias_register.csv` maps an `alias_id` to a `canonical_id`. Resolve
an identifier by following the mapping until an identifier is reached that
the register does not carry as an `alias_id`. That identifier is the
player identifier.

When the walk revisits an identifier it has already seen, the mapping is a
cycle. The player identifier of every member of a cycle is the
lexicographically lowest identifier in that cycle.

Two or more entry identifiers may resolve to one player identifier. They
form one cluster and the cluster is one entrant.

## Which filing governs

Take the rows of `entry_roster_register.csv` whose resolved identifier is
the player identifier. Keep only rows whose `entry_status` is in the
applicable list of the `entry_roster` section of `revision_precedence.toml`
and drop every row whose status is in the excluded list of that section. Of
the rows that remain take the one with the highest `revision_seq`, and
where two rows share that value take the one with the highest `entry_seq`.
That row is the governing filing. Its `entry_seq` is the `entry_seq` of the
entrant.

A withdrawn or voided row is out of scope whatever its `revision_seq` is.
An entrant whose rows are all out of scope is not an entrant of this event.

The cluster of an entrant is the distinct `entry_id` values of the rows
that remained in scope above. `folded_ids` is every member of the cluster
other than the player identifier, in ascending order, written as a JSON
array. An entrant whose cluster holds one identifier carries an empty
array.

## The division

The division of an entrant is the `division_id` of the governing filing. An
entrant whose division `division_topology.xml` does not carry with
`in_force` equal to `yes` is not an entrant of this event and appears in no
delivered document.

## The rating

Take the rows of `rating_return_sheet.psv` whose `player_ref` resolves to
the player identifier, keep only those whose `return_status` is in the
applicable list of the `rating_return` section of
`revision_precedence.toml`, and take the one with the highest `return_seq`.
When such a row exists the rating is quoted by that row and
`rating_source` is `return`. When no such row exists the rating is quoted
by the governing roster filing and `rating_source` is `roster`.

A quotation carries a value and a unit. Convert it into milli rating
through the entry of `unit_register_dictionary.toml` whose name is the
unit the quoting row carries: multiply the value by the numerator, divide
by the denominator and round half to even. The result is `rating_mr`.

A quotation whose value is the absent marker of `settlement_form_rules.toml`
is an absence. The rating of that entrant is the `default_rating_mr` of the
`division_admission_matrix.csv` row for the division of the entrant and
round one, and `rating_source` is `default`. An absence is never a zero.

## The seat order

`seed_number` is derived and never read. Order every entrant of this event
by `rating_mr` descending, and where two entrants share a rating by player
identifier ascending. The first entrant carries `seed_number` one and the
numbers run without a gap.

The `declared_seed` column of `seat_assignment_register.csv` is what the
hall published. It is not the seat order of this settlement.

## Delivered

`normalised_entries.jsonl`, one record per entrant in ascending player
identifier order.
