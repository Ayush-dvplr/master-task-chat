# Audit statistics

The audit block mixes figures taken from the replayed deployed run and from the
settled run. The definitions are deliberately not parallel; each name states its
own source, window and denominator.

- `deployed_recompiles_total`: recompile events over every step of the deployed
  replay
- `settled_recompiles_after_warmup`: recompile events of the settled run at steps
  strictly greater than its bound
- `deployed_distinct_capacity_values`: distinct per expert capacities over the
  deployed replay
- `settled_distinct_rank_buckets`: distinct rank bucket values over the settled
  run
- `deployed_drop_rate_assignment_denominator`: dropped assignments over total
  assignments, deployed replay
- `settled_drop_rate_token_denominator`: dropped assignments over total tokens,
  settled run
- `deployed_break_steps_inclusive_warmup`: steps with at least one break whose
  index is at most the deployed bound
- `settled_break_steps_exclusive_warmup`: steps with at least one break whose
  index is strictly greater than the settled bound
- `deployed_mean_host_bytes`: arithmetic mean over every deployed step
- `settled_peak_host_bytes`: maximum over every settled step
- `deployed_capture_failure_ratio`: failed capture attempts over all attempts
- `settled_capture_success_ratio`: successful captures over all attempts
- `deployed_empty_expert_step_count`: steps holding at least one empty expert
- `settled_empty_expert_slot_count`: pairs of a step and an empty expert, counted
  with repeats
- `deployed_unique_guard_keys_router_only`: distinct triples of code object, rank
  and key restricted to the router
- `settled_unique_guard_keys_moe_only`: the same count restricted to the expert
  regions
- `deployed_token_total`: tokens summed over every deployed step
