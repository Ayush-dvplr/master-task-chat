# P09 round scoring

Worked once per round, after P08 and before P10. Closes the round.

## The basis of an entrant

For each entrant eligible in the round, in this order:

- `bye` when P06 awarded it the bye.
- `void` when a candidate board of the round holds it and P08 voided that
  board.
- `match` when a candidate board of the round holds it and P08 left that
  board standing.
- `unpaired` when P07 left it unpaired.
- `no_record` when none of the above holds.

An entrant not eligible in the round has no row in this ledger and
contributes nothing to its running state.

When more than one candidate board of the round holds an entrant, the
board with the lowest `table_no` is the board of that entrant.

The magnitudes of the applicable notices of one class that name one round
are summed and the sum is applied once.

## The base points and the game differential

The point values of a round come from the applicable rows of
`round_configuration_register.csv` for that round and the division of the
entrant: `win_points`, `draw_points` and `loss_points`.

- `match`: the result P04 resolved, read from the side the entrant sits on.
  A `win_a` credits `win_points` to side a and `loss_points` to side b, a
  `win_b` the reverse, a `draw` credits `draw_points` to both and a
  `double_loss` credits `loss_points` to both. The game differential is the
  `delta_a` of P04 for side a and its negation for side b.
- `bye`: the `bye_points` and `bye_game_delta` clauses of
  `appeals_procedure_memo.pdf`.
- `void`: the `void_points` clause and a game differential of zero.
- `unpaired`: the `unpaired_points` clause and a game differential of zero.
- `no_record`: the `no_record_points` clause and a game differential of
  zero.

## The six steps of a round, in this order

1. The base points and the game differential above.
2. The game penalty class. Each applicable notice of
   `penalty_notice_register.psv` whose class is `game` and whose
   `effective_round` is this round takes its `magnitude` off the game
   differential. It reaches nothing else.
3. The match penalty class. When an applicable notice whose class is
   `match` names this round, the base points become the `loss_points` of
   the round. The result of the opponent is untouched and the game
   differential is untouched. `base_points` on the delivered ledger is the
   value after this step.
4. The round modifier. `modifier_code` is the value of the
   `round_configuration_register.csv` row for this round and division whose
   `parameter` is `modifier_code`. `modified_points` is `base_points`
   multiplied by the numerator of that code in `round_modifier_rules.json`,
   divided by its denominator and rounded half to even. The modifier
   reaches the match points alone and never the game differential.
5. The round penalty class. Each applicable notice whose class is `round`
   and whose `effective_round` is this round takes its `magnitude` off
   `modified_points`. The result is floored at the `round_points_floor`
   clause of `appeals_procedure_memo.pdf` and the shortfall is recorded by
   P10 and carried into no other round.
6. `round_points` is the value after step five and `game_delta` the value
   after step two. The round is now closed and its values are what P05 of
   the next round reads.

A notice of the `tournament` class reaches no round and is applied by P10.

## Delivered

`round_score_ledger.csv`, one row per eligible entrant and round, ascending
round then ascending player identifier.
