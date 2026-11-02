# P07 authoritative pairing

Worked once per round, after P06 and before P08.

## The pool

The pool is every entrant eligible in the round that P06 did not award the
bye to, across every division in force, held in one order. Order it on the
keys of the `pairing_order` family of
`standings_precedence_directive.docx`, applied in ascending key position.
The `division_rank` a key refers to is the rank of the division rank
register of the same directive.

## The ladder

`pairing_precedence_policy.toml` states four admission levels and that they
are cumulative: level one sets aside the constraint of the first rung of
`appeals_procedure_memo.pdf`, level two sets aside that rung and the
second, level three sets aside all three. Eligibility is never set aside.

A partner is admissible for a player at a level when every constraint the
level has not set aside holds:

- the division constraint: the two entrants are in the same division;
- the band constraint: the absolute difference of their `running_points` is
  at most the effective band;
- the prior opponent constraint: the partner is in no encounter of the
  player recorded by P11 in an earlier round, whether that encounter counts
  for strength or not.

The effective band is the `score_band` parameter of the live sheet of
`panel_capacity_workbook.xlsx` plus the `band_widening` parameter of the
`division_admission_matrix.csv` row for the division of the player taken
first and that round.

When the division constraint has been set aside and the two entrants are in
different divisions, the partner is admissible only when the
`cross_admitted` parameter of `division_admission_matrix.csv` is `yes` for
both divisions in that round. This gate is part of every level and no level
sets it aside.

## The search

Take the first entrant of the pool that is still unpaired. For level zero,
then level one, then level two, then level three, scan the entrants still
unpaired that follow it in the pool order and take the first admissible
one. The first level that yields a partner is the `admission_level` of the
board and the search stops there. Pair the two and continue with the next
unpaired entrant of the pool.

Board numbers run from one inside each round in the order the boards were
formed. `player_a` is the entrant taken first and `player_b` the partner.
`points_a` and `points_b` are their `running_points` at the opening of the
round.

An entrant no level yields a partner for is left unpaired. Its `reason` is
`no_admissible_partner`. It is credited the `unpaired_points` clause of
`appeals_procedure_memo.pdf` and a game differential of zero, and it
creates no opponent.

## Delivered

`authoritative_pairing_ledger.csv`, ascending round then ascending board.
`pairing_fallback_ledger.csv`, the boards whose `admission_level` is above
zero, with `relaxed_constraints` the rung names of
`appeals_procedure_memo.pdf` up to that level joined with a plus sign in
rung order. `unpaired_ledger.tsv`, ascending round then ascending player
identifier.

`pairing_constraint_report.json` carries one entry per round. `boards` is
the count of authoritative boards formed in the round, `byes` the byes P06
awarded, `unpaired` the entrants left unpaired and `level_counts` the
authoritative boards admitted at each level. `cross_division_boards` counts
the authoritative boards whose two entrants are in different divisions and
`repeat_boards` those whose two entrants are already in an encounter P11
recorded in an earlier round. `voided_boards` is the count of candidate
boards of the round P08 voided.
