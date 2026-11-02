# Stage r04 - policy layer resolution

Fed by: r01, r02, r03.
Feeds: r05, r09, r10.

Resolve the effective policy of every expanded instance.

- The layers and their ranks are in `precedence_directive.docx`
  part A, rank 1 the strongest. The fields are in
  `precedence_and_overturn.toml`. The layers are described below by
  name; this paper does not rank them.
- The mandatory layer applies when the directive schedule carries a
  row for this instance's action inside this instance's window. Among
  several such rows the greatest `seq` wins. The row records `tier`
  and `mandatory` and nothing else.
- The oneshot layer applies when an override for this action has
  remaining above zero and the trigger is strictly before its expiry.
  Remaining is read from `state_snapshot.json.oneshot_remaining`,
  which outranks the journal's own field. Among several applicable
  overrides the least override id wins. The override records only the
  fields it carries.
- The context layer applies when the instance's resolved context is
  active at the trigger, start inclusive and end exclusive. A context
  whose start equals its end is never active.
- The device layer is the live revision of `device_policies.csv` for
  the instance's resolved device, under RR1 with the device frozen
  revisions. Empty cells are absent fields.
- The action layer is `action_policies.jsonl` for the instance's
  action. The routine layer is `routine_defaults.toml` for the
  instance's routine, packed under RR8 as
  `tier|intensity_bp|cooldown_min|max_occurrences`. The global layer
  is `global_defaults.yaml` and records every field.
- For each field, the strongest applicable layer that records it
  settles it. A layer that does not record a field does not settle it.
- `layer_ranks` in `config_resolution.json` carries the directive's
  rank for every layer, keyed by layer name.
- After the layers have settled the cooldown, raise it to the live
  class floor in `cooldown_register.psv` for the action's class, if
  the floor is greater. The floor's live row is chosen under RR1
  against `state_snapshot.json.frozen_revision_cooldown_register`.
  When the floor raised the value, the winning layer recorded is
  `class_floor`.
- Publish `config_resolution.json` and `parameter_audit.csv`.
