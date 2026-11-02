# P13 standings and tiebreaks

## The order

Order every entrant of this event on the keys of the `tiebreak` family of
`standings_precedence_directive.docx`, applied in ascending key position,
each key in the direction the `ordering` list of `tiebreak_rules.json`
gives for it. The order is total because the last key is the player
identifier.

`rank` runs from one without a gap and no two entrants share a rank.

## Prize eligibility

`prize_eligible` is `no` when the `penalty_units` of the entrant reach the
`prize_disqualify_units` clause of `appeals_procedure_memo.pdf`, and `yes`
otherwise.

## The separating key

For each pair of entrants adjacent in the order, `separating_position` is
the lowest key position at which their values differ and `separating_key`
the `key_name` at that position. The last entrant has no row.

## Delivered

`standings_ledger.csv`, ascending rank. `tiebreak_resolution_ledger.csv`,
ascending rank. `final_ranking.json`, with the ranking in ascending rank.
