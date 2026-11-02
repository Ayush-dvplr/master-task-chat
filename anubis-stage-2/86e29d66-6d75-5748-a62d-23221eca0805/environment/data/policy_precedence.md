# Precedence policy

Four settings are resolved per record or per optimizer step rather than once per run:
the accumulation width, the partial window carry decision, the decay span and the
rate scale. Each one has its own layered rule. The layers are fixed; only the values
change between runs.

## Layer sources

* `profile` is the overlay named in the profile table. It is the outermost layer.
* `exception` is the entry of the restart exception table whose `restart_id` matches
  the restart that is currently in force at the sequence being resolved.
* `phase` is the entry of the phase table whose `phase` matches the phase that is open
  at the sequence being resolved.
* `policy` is the single accumulation policy document. It is the innermost layer and
  always has a value.

A restart is in force from its `at_sequence` until the next phase opening marker at a
strictly larger sequence. If no later marker exists, it stays in force to the end of
the run. A later restart replaces an earlier one. When no restart is in force, the
exception layer is absent and is skipped.

## Accumulation width

Resolution order, first layer that offers a value wins:

1. `profile.width_override`
2. `exception.accumulation_width`
3. `phase.accumulation_width`
4. `policy.default_width`

A `null` in any layer means that layer offers nothing and the next layer is consulted.
The resolved value is then clamped: raise it to `policy.minimum_width` if it is below,
then lower it to `policy.maximum_width` if it is above. Clamping happens once, after
resolution, never between layers.

Worked example. The policy default width is 4, phase `p3` carries width 5, restart
`rs-02` carries width 3 and the profile `peak` carries width override 6. A record at a
sequence where `p3` is open and `rs-02` is in force resolves to 3 under the profile
`visible` (exception beats phase) and to 6 under the profile `peak` (profile beats
exception). A record where only `p3` is open resolves to 5 under `visible`.

## Partial window carry

Resolution order, first layer that offers a value wins:

1. `profile.carry_partial` when it is `true` or `false`
2. `exception.carry_partial` when it is `true` or `false`
3. `policy.partial_window_rule`, where the string `carry` means carry and any other
   string means discard

A `null` means the layer offers nothing.

## Decay span

Resolution order:

1. `profile.decay_span_steps`
2. `schedule_base.decay_span_steps`

The phase table does not carry a decay span. The restart exception table does not
carry one either.

## Rate scale

The rate scales do not override one another. They compose, and the order of
composition is part of the result because each multiplication rounds. Starting from
the base rate for the step, apply:

1. `phase.rate_scale_percent` of the phase open at that step, when a phase is open
2. `profile.rate_scale_percent`
3. `exception.rate_scale_percent` of the restart in force at that step, when one is

Each application is the percent operation from the arithmetic policy. Applying the
same three percentages in a different order is a different number and is wrong.

Worked example. Base rate 1507 milli, phase scale 95, profile scale 90, no exception.
The phase step gives 1432 and the profile step then gives 1289. Applying the profile
scale first and the phase scale second gives 1288. Folding the two percentages into a
single division by 10000 also gives 1288. Only 1289 is the answer this policy names.

## Tie breakers

Every layer lookup that could be ambiguous has a named tie breaker, listed in the
ordering policy: phase markers that share a sequence, move rows that share an
effective sequence, and manifest rows that disagree about a shard.
