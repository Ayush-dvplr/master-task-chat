# P12 opponent strength

Worked once, after the last round closed. Every figure here is taken from
the closed event and never from a running state.

## The rate of an opponent

`rounds_counted` of an entrant is the number of rounds in which P09
published a row for it, whatever the basis of that row was.

The rate of an entrant is its `event_points` multiplied by the `rate_scale`
of `tiebreak_rules.json`, divided by its `rounds_counted` or by one when
that count is zero, rounded half to even. The rate is a whole number of
thousandths and it is the rounded value that the aggregate below consumes.

## The strength of an entrant

The population of an entrant is the distinct `opponent_id` values of its
encounter rows whose `counts_for_strength` is `yes`, across every round. An
opponent met twice appears in the population once.

`opponent_count` is the size of the population and `rate_sum` the sum of
the rates of its members. `opponent_strength` is `rate_sum` divided by
`opponent_count`, rounded half to even.

An entrant whose population is empty carries the `zero_strength_value` of
`tiebreak_rules.json` as its `opponent_strength`, with `opponent_count` and
`rate_sum` both zero.

## The penalty adjusted strength

`penalty_adjusted_strength` is `opponent_strength` less the `strength_debit`
parameter of the live sheet of `panel_capacity_workbook.xlsx` multiplied by
the `penalty_units` of the entrant, floored at zero.

## The game differential of the event

`raw_delta` is the sum, across every round of the entrant, of the game
differential of step one of P09, before the game penalty class reached it.
`game_penalty_units` is the summed `magnitude` of its applicable `game`
notices that named a round the entrant was eligible in. `adjusted_delta` is
`raw_delta` less `game_penalty_units`, and it equals the sum of the
`game_delta` P09 published. A differential of exactly zero is published as
zero and carries no sign.

## Delivered

`opponent_strength_ledger.csv`, ascending player identifier.
`game_differential_ledger.psv`, ascending player identifier.
