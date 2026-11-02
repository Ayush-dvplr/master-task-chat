# P08 admissibility and voids

Worked once per round, after P07 and before P09. Screens the candidate
boards of the round against what the regulations allowed.

## The tolerance of a board

The tolerance of a candidate board is the lower of the two admission
levels its two entrants were admitted at in P07 of that round.
`pairing_precedence_policy.toml` gives the tolerance of an entrant P06
awarded the bye to, of an entrant P07 left unpaired and of an entrant
that is not eligible in the round and so never entered P07.

## The screen

Each check below carries a violation level. A check whose violation level
is above the tolerance of the board voids it; a check whose violation level
is at most the tolerance does not.

| check | violation level | condition |
|---|---|---|
| `ineligible_player` | 4 | either entrant is not eligible in the round |
| `holds_bye` | 4 | either entrant is the entrant P06 awarded the bye to |
| `cross_division` | 3 | the two entrants are in different divisions |
| `repeat_opponent` | 2 | the two entrants are in an encounter P11 recorded in an earlier round |
| `score_band` | 1 | the absolute difference of their `running_points` exceeds the effective band of P07 |

A violation level of four is above every tolerance, so those two checks
always void.

## Which reason is recorded

More than one check may void one board. The reason recorded is the first
voiding check in the order of the `void_reason` family of
`standings_precedence_directive.docx`, applied in ascending key position.
That order is a precedence of reasons and it is not the rung order of the
pairing ladder.

`violation_level` is the violation level of the recorded reason.

## What a voided board credits

Each entrant of a voided board is credited the `void_points` clause of
`appeals_procedure_memo.pdf` and a game differential of zero, and `basis`
is `void`.

An entrant P06 awarded the bye to keeps the bye and its `basis` in P09
stays `bye`, so its `scored_a` or `scored_b` on this ledger is the
`base_points` P09 published for its bye. The other entrant of that board is
credited the void points like any other.

A candidate board no check voids stands, and the result P04 resolved for it
is what P09 scores.

`scored_a` and `scored_b` are the `base_points` P09 published for the two
entrants in that round, and the absent marker of
`settlement_form_rules.toml` for an entrant P09 published no row for.

The effective band this stage screens on is the `score_band` parameter of
the live sheet plus the `band_widening` of the division of the `player_a`
of the candidate board, in that round.

## Delivered

`void_adjudication_ledger.csv`, one row per voided board, ascending round
then ascending `table_no`.
