# Stage r13 - state transitions

Fed by: r12.
Feeds: r14.

Carry the surviving instances into state.

- Order the survivors by window ordinal, then trigger, then the
  action's position in the action order, then instance id.
- Walking that order, each instance sets its action's last fired time
  to its trigger and its cooldown until to trigger plus the resolved
  cooldown, and applies every row of `state_effects.jsonl` whose
  action is its own, in declared sequence order. The last write to a
  key wins, and the key records the trigger and action that wrote it.
- An instance to which a one shot override applied in r04 marks that
  override as consumed once, whichever layer settled its tier.
- Consumption never changes `remaining` within the cycle. r04 reads
  the snapshot's `remaining` for every instance of the day, however
  many earlier instances the same override applied to; the next
  state's `remaining` is the snapshot's less the consumption,
  floored at zero.
- This stage runs twice. The first pass is over the survivors of r12
  and publishes `cooldown_state.csv` and `derived_state.json`. The
  second pass is over the survivors of r14 and feeds
  `next_state_snapshot.json`. A one shot override is consumed only
  by the second pass, so an instance r14 withdraws never consumes it.
