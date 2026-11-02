# Stage r06 - dependency graph

Fed by: r01, r02.
Feeds: r07.

Build the dependency graph over actions.

- Resolve both endpoints of every edge under r02.
- Every edge takes the strength r01 recorded for its declared
  sequence. Drop an edge whose declared sequence recorded no
  strength, under `UNCONVERTIBLE_UNIT`.
- Drop an edge either of whose endpoints is not a catalogue action,
  under `UNRESOLVED_ENDPOINT`.
- Drop an edge whose endpoints are the same action, under
  `SELF_EDGE`.
- When two edges share a prereq and a dependent, keep one: its
  strength is the greater of the two and its declared sequence is the
  lesser. The later row is recorded as `DUPLICATE_EDGE`.
- Publish `dependency_graph.json`.
