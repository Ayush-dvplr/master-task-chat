# P05 round eligibility

Opens a round. Worked once per round, before the bye of that round.

## Who is eligible

An entrant is eligible in a round when the participation state of P02 for
that entrant and that round is `seated`. A `dropped`, an `absent` and a
`barred` entrant is not eligible. Eligibility is never set aside by any
rung of the pairing ladder and by no other rule of this settlement.

## The running state

`running_points` is the sum of the `round_points` P09 published for the
entrant in every round already closed, with no tournament penalty taken
off. `running_delta` is the sum of the `game_delta` P09 published for the
entrant in every round already closed. In round one both are zero.

The running state is the closed state. A round that has not closed
contributes nothing to the round it opens.

## Delivered

`round_eligibility_ledger.csv`, one row per entrant and round, ascending
round then ascending player identifier. `eligible` is `yes` or `no` and
`state` is the P02 state.
