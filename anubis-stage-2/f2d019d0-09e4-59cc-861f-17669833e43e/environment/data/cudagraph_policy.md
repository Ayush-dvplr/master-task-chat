# Graph capture

Capture is attempted once per guard key visited in the step, for expert regions
only. The router is never captured.

- When the compile mode is not `reduce-overhead` no capture is attempted and the
  recorded cause is `capture_disabled_for_mode`.
- When at least one graph break fired anywhere in the step the capture fails and
  the recorded cause is `operation_not_permitted_when_stream_is_capturing`.
- When any component of the key is `dyn` the capture fails and the recorded cause
  is `dynamic_dimension_in_guard_key`.
- Otherwise the capture succeeds and no cause is recorded.

## Pool

A step in which at least one capture succeeded grows the pool by the sum over
ranks of the block size chosen from `pool_block_table.csv`, taking the first row
whose `capacity_ceiling` is at least the `rank_bucket` of that rank. The pool is
cleared by a reset.

The reported figure for a step is the running peak, which is the larger of the
peak carried into the step and the pool size after the step. The running peak
restarts from the pool size of the step **after** the figure for that step has
been reported, so a reset step still publishes the peak reached before it.

## Graph breaks

Causes fire at most once per step. A cause fires when its condition holds:

- `data_dependent_capacity`: at least one capacity is not a multiple of
  `capacity_bucket`
- `dynamic_token_count`: the token count differs from the previous step and
  `tokens` is absent from `mark_dynamic`. The first step of a run never fires it
- `token_drop_mask`: at least one assignment was dropped
- `unbalanced_expert_slice`: the rank buckets are not all equal
- `zero_token_expert`: at least one expert recorded zero demand

The ledger lists fired causes in ascending cause name, which is the order of
`graph_break_catalog.csv`.
