# Stage r07 - cycle settlement

Fed by: r05, r06.
Feeds: r08.

Settle every cycle in the dependency graph.

- Cycles are legal. Find one under `cycle_break_policy.toml`, remove
  exactly one of its edges, and repeat until no cycle remains.
- The removable edge is chosen under the key order in
  `precedence_directive.docx` part B.
- The tier of a dependent action is the least resolved tier over the
  eligible instances of that action. An action with no eligible
  instance takes the global tier.
- `key_settled_at` is the ordinal of the first key in that order
  whose values are not all equal across all of the cycle's edges.
  It is a property of the cycle, not of the removed edge: a key on
  which the removed edge ties with some edges but not with others
  still settles the cycle. When the first three keys tie across
  every edge of the cycle the text key settles it and
  `key_settled_at` is `4`.
- The declared sequence is not unique. Rows of
  `dependency_edges.tsv` that describe different edges may share one,
  and r06 keeps them all, each at the strength r01 recorded for that
  declared sequence.
- Publish `cycle_break_ledger.json`.
