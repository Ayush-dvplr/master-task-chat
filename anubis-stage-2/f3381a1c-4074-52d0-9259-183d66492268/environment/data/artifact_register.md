# Artifact register, release R-NEXT

Every file below is written into the output directory. The register is part of
the handbook contract: the file name, the records, the keys, the record order
and the serialization are all fixed here.

Serialization rules:

- A `.jsonl` file holds one JSON object per line, keys sorted bytewise, no
  spaces after the separators (`json.dumps(record, sort_keys=True,
  separators=(",", ":"))`), one trailing newline per line and no blank lines. An
  empty artifact is an empty file.
- A `.json` file holds one object, keys sorted bytewise, two space indent, and a
  single trailing newline (`json.dumps(obj, indent=2, sort_keys=True)`).
- A `.csv` file is comma separated, LF terminated, with the header row stated
  below.
- `diagnosis.md` is Markdown prose.
- Every integer is a JSON integer. No field anywhere carries a float.

## normalized_inventory.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `base_cost_ticks`, `channel`, `component_id`, `kind`, `mandatory`, `pool_id`, `priority_class`, `priority_overridden`, `scope_tag`, `target_id`, `unit_id`.

## revision_delta.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `component_id`, `in_previous_release`, `previous_source_revision`, `source_changed`, `source_revision`, `target_id`, `unit_id`.

## toolchain_resolution.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `override_applied`, `previous_toolchain_revision`, `profile_id`, `toolchain_id`, `toolchain_revision`, `unit_id`.

## contract_delta.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `contract_changed`, `contract_revision`, `optional_interfaces`, `previous_contract_revision`, `required_interfaces`, `unit_id`.

## invalidation_reasons.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `dirty`, `reason_count`, `reasons`, `unit_id`.

## invalidation_closure.jsonl

Order: one record per dirty unit, in bytewise unit_id order.

Keys: `component_id`, `direct`, `kind`, `reasons`, `target_id`, `unit_id`.

## generated_output_plan.jsonl

Order: one record per interface, generated artifact kind and target that has a generating unit, ordered by interface_id, then artifact_kind, then target_id.

Keys: `artifact_kind`, `contract_revision`, `interface_id`, `previous_contract_revision`, `producer_unit`, `regenerate`, `supported`, `target_id`.

## build_unit_ledger.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `channel`, `component_id`, `contract_revision`, `kind`, `pool_id`, `reasons`, `required_dependencies`, `source_revision`, `state`, `target_id`, `toolchain_revision`, `unit_id`.

## build_cost_breakdown.jsonl

Order: one record per dirty unit, in bytewise unit_id order.

Keys: `after_cold_cache`, `after_platform`, `after_regeneration`, `base_cost_ticks`, `cold_cache_applied`, `cost_ticks`, `minimum_cost_ticks`, `platform_denominator`, `platform_numerator`, `regeneration_applied`, `unit_id`.

## capacity_allocation.jsonl

Order: one record per selected unit, in bytewise unit_id order.

Keys: `admitted_with`, `cost_ticks`, `pool_id`, `priority_class`, `unit_id`.

## deferred_units.jsonl

Order: one record per deferred unit, in bytewise unit_id order.

Keys: `cost_ticks`, `pool_id`, `priority_class`, `reason_code`, `unit_id`.

## dependency_schedule.jsonl

Order: one record per scheduled unit, in ascending sequence order.

Keys: `cost_ticks`, `dependencies`, `pool_id`, `priority_class`, `sequence`, `unit_id`.

## cycle_resolution.jsonl

Order: one record per resolved cycle, ordered by target_id, then group_id, then edge_removed.

Keys: `break_cost`, `edge_removed`, `group_id`, `members`, `policy`, `target_id`, `units_blocked`.

## worker_pool_summary.json

Order: one object, pools keyed by pool_id.

Keys: `pools`, `release_id`.

Each value of `pools` carries: `consumed_ticks`, `deferred_units`, `gross_budget_ticks`, `net_budget_ticks`, `operational_lanes`, `remaining_ticks`, `reserved_ticks`, `selected_units`.

## compatibility_matrix.jsonl

Order: one record per selected pair of a resolved cluster, ordered by cluster_id, then left_component, then right_component.

Keys: `cluster_id`, `compatible`, `left_component`, `left_version`, `right_component`, `right_version`.

## rejected_combinations.jsonl

Order: one record per rejected combination, ordered by cluster_id, then preference_sum, then the version list.

Keys: `cluster_id`, `members`, `preference_sum`, `reason`, `versions`.

## version_selection.jsonl

Order: one record per selected component version, ordered by component_id, then cluster_id.

Keys: `api_revision`, `cluster_id`, `component_id`, `local_preference`, `preference_sum`, `version`.

## release_membership.jsonl

Order: one record per unit, in bytewise unit_id order.

Keys: `pool_id`, `reason_code`, `state`, `target_id`, `unit_id`.

## deployment_manifest.json

Order: one object; members in bytewise unit_id order.

Keys: `decision`, `member_count`, `members`, `release_id`.

Each record of `members` carries: `component_id`, `contract_revision`, `kind`, `target_id`, `unit_id`, `version`.

## generated_sdk_manifest.jsonl

Order: one record per regenerated output of a selected generating unit, ordered by producer_unit, then interface_id, then artifact_kind.

Keys: `artifact_kind`, `contract_revision`, `interface_id`, `producer_unit`, `producer_version`.

## migration_order.jsonl

Order: one record per active migration_first constraint whose two units are both selected, ordered by migration_unit, then blocks_unit.

Keys: `blocked_sequence`, `blocks_unit`, `migration_sequence`, `migration_unit`, `ordered`, `target_id`.

## artifact_provenance.jsonl

Order: one record per selected unit, in bytewise unit_id order.

Keys: `contract_revision`, `cost_ticks`, `pool_id`, `reasons`, `schedule_sequence`, `source_revision`, `toolchain_revision`, `unit_id`.

## cache_reuse_manifest.jsonl

Order: one record per reusable unit, in bytewise unit_id order.

Keys: `artifact_digest`, `justification`, `reusable`, `unit_id`.

## release_delta.json

Order: one object; every unit list sorted bytewise.

Keys: `added_count`, `added_units`, `previous_release_id`, `release_id`, `removed_count`, `removed_units`, `retained_count`, `retained_units`.

## audit_exceptions.jsonl

Order: one record per exception, ordered by code, then subject, then detail.

Keys: `code`, `detail`, `subject`.

`code` is the exception code the handbook or an addendum names for the case.
`detail` is free prose and carries no fixed wording. `subject` is fixed here,
per code, together with how many records the case produces:

| code | subject | records |
|------|---------|---------|
| `E_ID_FORM` | the identifier text as it was written, with padding stripped | one per ignored row |
| `E_NON_INTEGER` | the component for a register row, the pool for a budget row, the unit for a platform scaling row | one per ignored row |
| `E_UNKNOWN_UNIT` | the identifier that names no row of its register, which is the component or the target itself and never the unit or the row carrying it | one per missing identifier per ignored row |
| `E_UNKNOWN_POOL` | the pool identifier the offending row names | one per offending row, so a pool named by both a budget row and a maintenance window is recorded twice |
| `E_NOT_ELIGIBLE` | the unit the eligibility table refuses | one per refused pair |
| `E_ARTIFACT_MISSING` | the unit whose previous artifact is absent or not retained | one per unit |
| `E_SDK_UNSUPPORTED` | `<interface_id>@<unit_id>` of the generating unit | one per generated output row whose regeneration the support matrix refuses |
| `E_PROHIBITED`, `E_REVIEW_HELD`, `E_CHANNEL_FROZEN` | the prohibited unit | one per unit |
| `E_CAPACITY`, `E_PREREQ_DEFERRED`, `E_CYCLE_BLOCKING` | the unit that leaves the release | one per unit |
| `E_ORDER_IGNORED` | `<before_unit>-><after_unit>` of the dropped edge | one per dropped edge |
| `E_WITHDRAWN_VERSION` | the component with no supported version | one per component |
| `E_CLUSTER_UNRESOLVED` | the unresolved cluster | one per cluster |

## cost_amortization.jsonl

Order: one record per producer unit, interface and consumer that takes a share, ordered by producer_unit, then interface_id, then consumer_component.

Keys: `consumer_component`, `interface_id`, `producer_unit`, `remainder_rank`, `share_ticks`, `target_id`.

## release_decision.json

Order: one object; every unit list sorted bytewise.

Keys: `blocked_targets`, `decision`, `exception_count`, `mandatory_units_withheld`, `release_id`, `scheduled_units`, `total_cost_ticks`, `units_blocked`, `units_built_not_published`, `units_deferred`, `units_excluded`, `units_included`, `units_reused`, `units_total`, `unresolved_clusters`.

## conformance_summary.csv

Order: header row metric,value then one row per metric in the order listed below.

The metric rows, in this exact order:

    units_total, units_included, units_built_not_published, units_reused,
    units_deferred, units_blocked, units_excluded, scheduled_units,
    total_cost_ticks, exception_count, decision

Each row is `metric,value`. The last row carries the release decision.

## diagnosis.md

One numbered entry per defect of the retired planner that the corrected program
fixes. Each entry names the handbook or addendum rule the defect broke.
