# P10 penalty application

Publishes every applied notice and settles the tournament class.

## Which notices are applied

An applicable row of `penalty_notice_register.psv` is one whose
`event_reference` is this event, whose `player_ref` resolves to an entrant
of this event and whose `notice_status` is in the applicable list of the
`penalty_notice` section of `revision_precedence.toml`. A `rescinded`
notice is out of scope whatever its `notice_seq` is.

`appeal_disposition_journal.jsonl` records how the panel disposed of a
notice. It changes no notice and it is published nowhere; a notice is
applicable on its own `notice_status` alone.

The four applied classes are the sequence of the `order` section of
`penalty_precedence_policy.toml`, which is the same order the
`penalty_order_1` to `penalty_order_4` clauses of
`appeals_procedure_memo.pdf` print.

## What each row carries

One row is written per applied class that reached an entrant in a round.
`magnitude` is the summed magnitude of the applicable notices of that class
naming that round and `notice_seq` the lowest `notice_seq` among them.

- `game`: `value_before` is the game differential of the round before the
  notice, `value_after` the value after it, `shortfall` zero.
- `match`: `value_before` is the base points before the notice,
  `value_after` the `loss_points` of the round, `shortfall` zero.
- `round`: `value_before` is `modified_points`, `value_after` the floored
  round points, `shortfall` the magnitude less `value_before` when the
  magnitude is the larger and zero otherwise.
- `tournament`: `round_no` is zero, because the class reaches the event
  total and no round. `value_before` is the sum of the `round_points` of
  the entrant across every round, `value_after` that sum less the magnitude
  floored at zero, `shortfall` the magnitude less the sum when the
  magnitude is the larger and zero otherwise.

A notice whose class is `expulsion` is not one of the four applied classes.
It has no row here; it reaches the participation state of P02.

A `game`, `match` or `round` notice whose `effective_round` names a round
the entrant was not eligible in has no row here and reaches nothing. A
`tournament` notice reaches the event total whatever the state of the
entrant in the round it names, because the class reaches no round.

## The event total

`event_points` of an entrant is the sum of its `round_points` less the
summed `magnitude` of its applicable `tournament` notices, floored at zero.
`penalty_units` of an entrant is that summed magnitude.

## Delivered

`penalty_application_ledger.psv`, ascending `round_no` then ascending
player identifier then the applied class order.
