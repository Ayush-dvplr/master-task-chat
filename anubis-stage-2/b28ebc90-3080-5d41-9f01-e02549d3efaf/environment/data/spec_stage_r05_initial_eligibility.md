# Stage r05 - initial eligibility

Fed by: r04, r03.
Feeds: r07, r08, r14.

Decide which expanded instances are eligible before any capacity is
considered.

- `last_fired_ms` for an action is the snapshot value when the
  snapshot records one, otherwise the `last_fired_ms` of that action
  in the archive table named by `assistant_runtime.conf`, otherwise
  it is absent.
- `suppressed_until_ms` is the snapshot value or zero.
- A carried cooldown is the greatest `carried_cooldown` in
  `prior_cycle_journal.jsonl` whose `cycle_index` equals the runtime's
  preceding cycle index, for this action. When one exists the
  cooldown in force is the greater of the resolved cooldown and the
  carried one.
- An instance is withheld under `SUPPRESSED` when its resolved
  `suppress` is true, or when its trigger is below
  `suppressed_until_ms`.
- An instance is withheld under `COOLDOWN` when a last fired time is
  known and `trigger - last_fired` is below the cooldown in force.
  Equality is eligible.
- Publish `trigger_eligibility_index.json`.
