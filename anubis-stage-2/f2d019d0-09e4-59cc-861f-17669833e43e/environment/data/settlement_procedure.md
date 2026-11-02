# Settlement

The candidate space is the full cross product of the four axes in
`capacity_candidates.json`. Every candidate keeps every other setting of the run
it replaces and is evaluated over the leading `probe_steps` steps, with the reset
list truncated to that horizon.

Each candidate is compared against an eager reference sharing its capacity factor
and bucket. Those references may be reused across candidates.

## Pre filter

A candidate is removed before any rejection cause is considered when it fails to
mark a dimension that the warmup profile listed in `dims_requiring_dynamic`. Such
candidates are published under `prefiltered` with the sorted list of unmarked
dimensions and they never reach the cause counts.

## Causes

A surviving candidate is checked against seven conditions.

- `eager_mode_forbidden`: the compile mode is `eager`
- `recompile_budget_exceeded`: recompiles after warmup exceed `recompile_budget`
- `speedup_gate_unmet`: the measured speedup is below `min_speedup`
- `memory_ceiling_exceeded`: the smallest headroom is negative
- `drop_tolerance_exceeded`: the drop rate exceeds `max_drop_rate`
- `convergence_band_unmet`: the relative deviation exceeds
  `settlement_parity_band`, which is the tighter of the two bands recorded in the
  convergence gate file and is used here and nowhere else
- `capacity_below_minimum`: the smallest capacity is below `capacity_floor`

The drop rate divides dropped assignments by total assignments.

A candidate violating nothing is admissible. A candidate violating anything is
attributed to the **first** cause in the precedence order that it violates, and
only that cause. Every one of the seven causes appears in the count map, with a
zero when no candidate is attributed to it. The precedence order is fixed for this pipeline and is not
printed in this document. `precedence_constraints.md` narrows it and
`sealed_policy_notes.md` pins it down.

## Selection

Among the admissible candidates, order by ascending capacity factor, then by
descending bucket, then by the number of marked dimensions ascending, then by the
marked dimensions joined with a vertical bar ascending, then by compile mode
**descending**. The first entry settles. The last key runs the other way from the
four before it.

A candidate label is written
`cf=<factor>|bucket=<bucket>|dynamic=<marks>|mode=<mode>` where the factor is the
Python repr of the float, the marks are joined with a plus sign and an empty set
is written `none`.
