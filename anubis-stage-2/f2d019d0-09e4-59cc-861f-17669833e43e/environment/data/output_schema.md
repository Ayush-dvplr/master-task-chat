# Published records

Every record is a JSON object serialised with two space indentation, keys sorted
at every level, no ASCII escaping, and exactly one trailing newline. Integers are
written as integers. Floats are rounded as the numeric contract requires. A field
documented as absent is absent, not null, unless the contract says null.

Integers, floats and booleans are not interchangeable. A float whose value is
whole is still a float and is written with a trailing `.0`. Counts, step and
token indices, ranks, capacities, buckets, slot figures, guard deltas, the per
step `captured` count and byte figures are integers, except that a mean of bytes
is a float. Losses, masses, logits, outputs, partials, signals, gradients,
parameters, norms, factors, scales, rates, ratios, slopes, deviations, bands,
targets, timings, speed margins, every `signed_delta` and every residual are
floats. A configuration setting, whether it is published under its own name or
as a `value`, a `from`, a `to` or a `delta`, keeps the JSON type that setting
has in `deployed_config.json`. A figure copied from `deployed_run_summary.json` keeps
the type it has there. A yes or no outcome is a boolean.

Each record carries exactly the top level keys listed for it here, no more and no
fewer.

- `route_plan.json`: `run_id`, `top_k`, `tie_break_key`, `steps`,
  `tie_break_events`, `total_assignments`. Each entry of `steps` carries `step`,
  `token_count`, `demand`, `gate_mass_total`, `tie_break_count`. Each entry of
  `tie_break_events` carries `step`, `token_index`, `quantized_logit`,
  `contenders`, `selected`. `gate_mass_total` is formed from the balance term
  probabilities of that step under the sourcing in force: they are added in
  ascending expert index with no rounding between additions, the sum is
  multiplied by `token_count`, and the product is rounded once. It is not the
  count of assignments and it is not the sum of the unrounded gate masses, so it
  can differ from a whole number in its last places.
- `capacity_plan.json`: `run_id`, `capacity_factor`, `capacity_bucket`,
  `min_capacity`, `steps`, `min_capacity_seen`, `max_capacity_seen`,
  `distinct_capacity_values`. Each step entry carries `step`, `capacity`,
  `unaligned_experts`.
- `mesh_plan.json`: `run_id`, `ep_world_size`, `expert_rank`, `rank_experts`,
  `placement_groups`, `rank_bucket_by_step`, `expert_shape_matrix`. The last of
  those is a single number, the count of distinct capacity vectors multiplied by
  the number of expert layers. `rank_experts` is keyed by rank. Each entry of
  `rank_bucket_by_step` carries `step` and `rank_bucket`, the latter keyed by
  rank.
- `dispatch_ledger.json`: `run_id`, `steps`, `total_accepted`,
  `total_padded_slots`. Each step entry carries `step`, `accepted_count`,
  `padded_slots`.
- `drop_ledger.json`: `run_id`, `steps`, `dropped_tokens`, `dropped_token_mass`,
  `drop_rate`, `steps_with_drops`. Each step entry carries `step`,
  `dropped_tokens`, `dropped_token_mass`.
- `alltoall_ledger.json`: `run_id`, `ep_world_size`, `steps`, `uniform_steps`,
  `total_payload_slots`. Each step entry carries `step`, `alltoall_bucket`,
  `payload_slots`, `rank_bucket_spread`.
- `guard_key_index.json`: `run_id`, `keys_by_slot`, `distinct_key_count`,
  `specialized_zero_one_keys`, `dynamic_dims_final`.
- `recompile_report.json`: `run_id`, `warmup_bound`, `recompile_events`,
  `total_recompiles`, `recompiles_after_warmup`, `first_step_over_budget`,
  `evictions`, `recompiles_by_step`. The events list holds objects, each carrying
  `step`, `code_object`, `rank`, `guard_key`, `guard_delta`, `evicted_key`.
  Each entry of `recompiles_by_step` carries `step`, `count`.
- `graph_break_ledger.json`: `run_id`, `cause_order`, `per_cause_counts`,
  `steps`, `total_breaks`, `clean_steps`. `per_cause_counts` is keyed by cause
  name. Each step entry carries `step`, `causes`.
- `cudagraph_report.json`: `run_id`, `compile_mode`, `capture_attempts`,
  `captures`, `failure_causes`, `steps`, `final_pool_peak_bytes`, `reset_steps`.
  `failure_causes` is keyed by cause name. Each step entry carries `step`,
  `captured`, `pool_bytes`, `pool_peak_bytes`.
- `host_memory_report.json`: `run_id`, `host_ceiling_bytes`, `steps`,
  `min_host_headroom_bytes`, `peak_host_bytes`, `steps_over_ceiling`,
  `memory_gate_met`. Each step entry carries `step`, `host_bytes`,
  `host_headroom_bytes`, `cache_entries`, `guard_closures`.
- `steptime_report.json`: `run_id`, `steps`, `gated_step_range`,
  `compiled_tail_us`, `eager_tail_us`, `speedup`, `min_speedup`,
  `speedup_gate_met`, `amortized_compile_us`. Each step entry carries `step`,
  `step_us`, `compute_us`, `alltoall_us`, `compile_us`, `capture_us`,
  `bubble_us`, `eager_step_us`.
- `warmup_profile.json`: `run_id`, `warmup_bound`, `window_steps`,
  `distinct_token_values`, `distinct_capacity_values`,
  `distinct_local_expert_values`, `promotion_threshold`,
  `dims_requiring_dynamic`, `warmup_recompiles`.
- `sealed_policy_resolution.json`: `tie_break_key`, `tie_break_matches`,
  `tie_break_candidates_enumerated`, `precedence_order`, `precedence_matches`,
  `precedence_candidates_enumerated`, `sealed_configs`.
- `aux_loss_trace.json`: `run_id`, `aux_loss_weight`, `steps`, `aux_loss_total`,
  `steps_with_empty_experts`, `mean_load_dispersion`. Each step entry carries
  `step`, `aux_loss`, `expert_utilization`, `load_dispersion`, `empty_experts`.
- `loss_curve.json`: `run_id`, `steps`, `closing_loss`, `opening_loss`,
  `minimum_loss`, `steps_above_opening`. Each step entry carries `step`, `loss`,
  `eager_loss`, `signed_gap`.
- `gradient_ledger.json`: `run_id`, `steps`, `folded_signal`, `final_params`,
  `accumulation_order`. Each step entry carries `step`, `expert_outputs`,
  `expert_partials`, `step_signal`, `gradients`. `accumulation_order` is the
  list `["slot_ascending", "expert_index_ascending"]`, naming the inner walk of
  the numeric contract first and the outer walk second.
- `optimizer_trace.json`: `run_id`, `loss_scale`, `clip_threshold`,
  `learning_rate`, `steps`, `clipped_steps`, `clipped_step_count`. Each step
  entry carries `step`, `scaled_norm`, `clip_reference`, `clip_factor`,
  `clipped`.
- `convergence_report.json`: `run_id`, `slope_window`, `windowed_slope`,
  `closing_loss`, `baseline_closing_loss`, `relative_deviation`, `parity_band`,
  `parity_holds`, `target_loss`, `verdict`. With `losses` the per step compiled
  losses of the settled run and `w` the `slope_window` of
  `convergence_gates.json`, `windowed_slope` is
  `(losses[-1] - losses[-w]) / (w - 1)` when the run has at least `w` steps and
  `w` exceeds one, and `losses[-1] - losses[0]` otherwise, rounded once.
  `closing_loss` is the last compiled loss and `baseline_closing_loss` the last
  eager loss. `relative_deviation` is the absolute difference of the two divided
  by the absolute eager figure, rounded, and zero when the eager figure is zero;
  the settlement gate figures and the run summaries use the same formula.
  `parity_holds` is true when that deviation is at most `parity_band`.
  `verdict` is the string `met` when parity holds, `windowed_slope` is at most
  `max_slope` and `closing_loss` is at most `target_loss`, and the string
  `unmet` otherwise.
- `baseline_parity.json`: `run_id`, `steps`, `max_relative_deviation`,
  `max_deviation_step`, `parity_band`, `parity_holds`, `steps_outside_band`.
  Each step entry carries `step`, `relative_deviation`, computed per step with
  the convergence formula. `max_deviation_step` is the first step attaining the
  largest deviation and is null when every deviation is zero. `parity_holds` is
  true when the largest deviation is at most `parity_band`, and
  `steps_outside_band` lists in ascending order the steps whose deviation
  exceeds it.
- `settlement_report.json`: `run_id`, `probe_steps`, `candidates_evaluated`,
  `prefiltered_count`, `rejected_count`, `admissible_count`,
  `settled_configuration`, `settled_gate_figures`, `changed_settings`,
  `gates_met`. `settled_configuration` carries `capacity_factor`,
  `capacity_bucket`, `mark_dynamic`, `compile_mode`. `settled_gate_figures`
  and `gates_met` describe the settled configuration replayed over the full step
  count of the run it replaces, never over the probe horizon. `gates_met`
  carries `speedup`, true when the speedup is at least `min_speedup`; `memory`,
  true when the smallest host headroom is zero or more; `recompile_budget`, true
  when the recompiles after warmup are at most `recompile_budget`; and
  `convergence`, true when the relative deviation is at most `parity_band`.
  `settled_gate_figures` carries `speedup`, `compiled_tail_us`,
  `eager_tail_us`, `min_host_headroom_bytes`, `recompiles_after_warmup`,
  `drop_rate`, `min_capacity_seen`, `closing_loss`, `baseline_closing_loss`,
  `relative_deviation`. Each entry of `changed_settings` carries `setting`,
  `from`, `to`.
- `rejection_ledger.json`: `cause_order`, `per_cause_counts`, `rejected`,
  `prefiltered`, `admissible_candidates`. `per_cause_counts` is keyed by cause
  name. Each entry of `rejected` carries `candidate`, `cause`,
  `all_violations`.
- `sensitivity.json`: `run_id`, `probe_steps`, `perturbations`,
  `negative_speedup_margins`, `negative_headroom_margins`. Each entry of
  `perturbations` carries `setting`, `delta`, `speedup_margin`,
  `headroom_margin`, `recompile_margin`.
- `audit_statistics.json`: the seventeen names listed in `audit_definitions.md`.
- `deployed_diagnosis.json`: `run_id`, `published_vs_replayed`,
  `departing_settings`, `capture_failure_causes`, `first_step_over_budget`,
  `admissible`, `published_agrees_with_replay`. `published_vs_replayed` is keyed
  by `speedup`, `closing_loss`, `drop_rate`, `min_host_headroom_bytes`,
  `total_recompiles`, `recompiles_after_warmup`, and each of its entries carries
  `published`, `replayed`, `signed_delta`. Each entry of `departing_settings`
  carries `setting`, `value`, `policy`, `revision`. `signed_delta` is the
  published figure minus the replayed figure, rounded to `float_decimals` for
  every field including `speedup`. `admissible` is true
  exactly when `departing_settings` is empty and the corrected replay of the
  deployed configuration over its whole run triggers none of the rejection
  causes of `settlement_procedure.md`; it is false otherwise.
- `validation_report.json`: `residuals`, `record_counts`,
  `max_absolute_residual`, `artifact_count`, `float_decimals`,
  `time_decimals`. `residuals` is keyed by `speedup`, `closing_loss`,
  `drop_rate`, `min_host_headroom_bytes`, `recompiles_after_warmup`. Each
  residual is the published figure of `deployed_run_summary.json` minus the
  same figure of the corrected deployed replay, rounded to `float_decimals` for
  every field including `speedup`, and
  `max_absolute_residual` is the largest absolute residual, zero when there is
  none. `record_counts` is keyed by record file name and covers the
  twenty-five records listed above `validation_report.json`. A record whose
  `steps` is a list counts its step entries; any other record counts its top
  level keys. `artifact_count` is the number of records `record_counts` covers.
- `stage_manifest.json`: `stage`, `artifact_count`, `artifact_sha256`.
- `replay_manifest.json`: `stage`, `artifact_count`, `artifact_sha256`,
  `stage_manifest_sha256`.
- `final_state.json`: `closing_loss`, `convergence_verdict`,
  `deployed_admissible`, `digest_of_digests`, `first_step_over_budget`,
  `precedence_order`, `replay_manifest_sha256`, `settled_configuration`,
  `settlement_salt`, `speedup`, `stage_manifest_sha256`, `tie_break_key`,
  `total_artifacts`.

The stage manifest digests the fourteen dispatch and compile records. The replay
manifest digests the twelve replay and settlement records and additionally
carries the SHA-256 of the canonical bytes of the stage manifest as written to
disk. The final state folds a map of three entries, keyed `replay`, `salt` and
`stage`, holding the replay manifest digest, the digest of the settled
configuration object and the stage manifest digest.

The fourteen dispatch and compile records are `route_plan.json` through
`sealed_policy_resolution.json` in the order listed above, and the stage manifest
carries `stage` set to `dispatch_and_compile`. The twelve replay and settlement
records are `aux_loss_trace.json` through `validation_report.json` in the order
listed above, and the replay manifest carries `stage` set to
`replay_and_settlement`. In each manifest `artifact_count` is the number of
records it digests and `artifact_sha256` is keyed by record file name, one entry
per digested record. `total_artifacts` counts every record named in this file.

The records describing routing, capacity, the mesh, dispatch, drops, the
collective, guard keys, recompiles, breaks, capture, host memory, step time and
the warmup profile describe the deployed configuration replayed against the
contracts in force. The records describing the balance term, the loss, gradients,
the optimizer, convergence and parity describe the settled configuration.

# Document verbs

A document is a JSON object with exactly two keys. `config` is a run
configuration carrying the same keys as `deployed_config.json`. `tables` is an
object keyed by file name that holds one entry for every `.json`, `.jsonl` and
`.csv` file of the corpus. A `.json` entry holds the parsed value of that file.
A `.jsonl` entry holds the list of its parsed lines in file order. A `.csv`
entry holds the list of its rows in file order, each row an object keyed by the
header with every cell kept as a string, blank lines dropped. The prose files
are not carried. The configuration names its schedule through `seq_profile`, and
its rows are the rows of `seq_length_schedule.csv` carrying that profile.

Each verb prints one canonical JSON object with exactly these top level keys.
A key that names a record holds that record, computed for `config`.

- `trace`: `tie_break_key`, `tie_break_matches`, `guard_key_index`,
  `recompile_report`, `graph_break_ledger`, `cudagraph_report`,
  `capacity_plan`, `mesh_plan`, `host_memory_report`, `warmup_profile`.
- `replay`: `tie_break_key`, `tie_break_matches`, `route_plan`,
  `dispatch_ledger`, `drop_ledger`, `alltoall_ledger`, `aux_loss_trace`,
  `loss_curve`, `gradient_ledger`, `optimizer_trace`, `convergence_report`,
  `baseline_parity`, `steptime_report`.
- `settle`: `rejection_ledger`, `warmup_profile`, `settled_configuration`,
  `probe_steps`.
- `resolve`: the keys of `sealed_policy_resolution.json`.
