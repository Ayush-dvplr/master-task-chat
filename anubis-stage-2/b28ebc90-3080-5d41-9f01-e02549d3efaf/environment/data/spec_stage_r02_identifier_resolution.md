# Stage r02 - identifier resolution

Fed by: r01.
Feeds: r03, r04, r06.

Bind every alias and resolve every `_ref` column.

- Take every identifier source named in `source_priority_register.csv`
  whose status is `in_force`: `alias_crosswalk.tsv` and
  `identifier_supplement.psv`. A source not named there, or named and
  withdrawn, contributes nothing.
- Order the rows of all in force sources by source rank ascending,
  then declared sequence ascending, then alias ascending.
- Walk that order. A row whose alias equals its canonical name is a
  `self` decision and binds nothing. A row whose alias is already
  bound is a `collision` decision and binds nothing. Any other row is
  a `bound` decision and binds the alias.
- Resolving a name follows bindings until a name that is not bound is
  reached, up to the alias hop cap. If a name repeats before then,
  the resolution is a `cycle` and the name resolves to itself. A
  repeat reached by the very hop that uses up the cap still counts.
  When the cap is used up with no repeat, the name reached by then
  is the resolution, even though it is still bound.
- A `bound` or `cycle` decision's `hops` is `0` when the alias
  resolves to itself and `1` otherwise, and its `canonical` is the
  name the alias finally resolves to, not the name its own row
  recorded. A `self` or `collision` decision binds nothing, so it
  keeps the canonical its own row recorded and its `hops` is `0`.
- Build the window grid from `window_grid.csv` under RR1 and RR6,
  the device grid from `device_register.csv` under RR1, and the
  context grid from `context_activity_spans.tsv` under RR5 and RR6.
  A context row whose identifier is not a bare context id carries the
  chain forward and is not itself a context.
- Publish `alias_resolution.jsonl`.
