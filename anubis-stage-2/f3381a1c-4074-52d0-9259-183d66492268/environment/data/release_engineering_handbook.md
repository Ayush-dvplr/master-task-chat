# Release engineering handbook, release R-NEXT

This handbook is the authority for the release train build. Where any other
file in this directory disagrees with it, the handbook wins, with two named
exceptions that are themselves part of this contract:

- `rounding_precedence_addendum.pdf` (addendum A) is the authority for the cost
  scaling order, the ceiling rule, pool budget conversion, the admission order
  and selection objective, cross pool prerequisites, cycle breaks, the schedule
  tie break, and the priority class overrides it tabulates.
- `compatibility_window_notes.docx` (addendum B) is the authority for version
  windows, the version selection rule and the publication review and channel
  freeze prohibitions.

The retired planner (`legacy_planner.py`, `legacy_cost_helpers.py`) and its last
output (`retired_run_report.json`) are kept for comparison only. They are not a
specification and none of their figures can be trusted. `legacy_notes.md`
records what the retired planner was believed to do, not what it did.

`previous_build_timings.csv` records what the previous release actually cost in
wall time. Observed cost never feeds planning; it is reporting only, and so is
every column whose name begins `legacy_` or `observed_`.

## 1. Identity

A release unit is one component built for one target. Its identity is the tuple

    (component_id, target_id, source_revision, toolchain_revision,
     contract_revision)

and its canonical name, used in every output, is `component_id:target_id`, for
example `C-0123:T-04`.

A component identifier is `C-` followed by four digits. A target identifier is
`T-` followed by two digits. An interface identifier is `IF-` followed by three
digits. A pool identifier starts `P-`. Identifiers are compared bytewise and
case sensitively, and every sort in this handbook is a bytewise ascending sort
unless it says otherwise.

## 2. Reading a row

Every shipped table is read under these rules. Each rule has an exact inverse
and `normalization_cases.jsonl` carries a worked example of each.

1. An identifier may arrive padded with spaces. Strip the padding before
   matching.
2. An identifier that is not in the canonical form above, including one written
   in lower case, makes its row invalid. The row is ignored and the exception
   `E_ID_FORM` is recorded against the stripped text.
3. An integer may be written with underscore digit grouping (`1_200`). It is an
   ordinary integer.
4. A tick field carrying a decimal point is not an integer. The row is ignored
   and `E_NON_INTEGER` is recorded.
5. A row whose `status` or `state` column reads anything other than `active` is
   not applied. `superseded` is the common case and means the row has been
   replaced.
6. Two active rows may carry the same key. The row with the greater
   `revision_seq` wins; if those are equal the row with the bytewise greater
   `row_id` wins. This is how a correction replaces an earlier row, and it is
   also how an artifact index entry revokes retention.
7. A field whose name ends `_millis` is in thousandths of a tick. Convert it
   with `ceil(value / 1000)` before use. A field whose name ends `_ticks` is
   already in ticks.
8. An optional build dependency applies to a target only when
   `optional_dependencies.jsonl` carries an active row for that dependent,
   dependency and target with `activated` true.
9. An identifier that names no row of its register is ignored and
   `E_UNKNOWN_UNIT` is recorded. A pool that names no row of the pool register
   is ignored and `E_UNKNOWN_POOL` is recorded.
10. A missing optional field, an explicit null and an absent row are three
    different things. A missing field takes the default this handbook states for
    it; an absent row contributes nothing at all.

An empty group is legal and produces a valid empty output. A group of one
member is legal and is not a special case.

## 3. Stage 1, the normalized inventory

A unit exists when all of the following hold.

1. `component_register.csv` carries an active row for the component, read under
   section 2, and that row's `base_cost_ticks` is an integer. A base cost of 0
   is legal.
2. `target_matrix.csv` carries an active row for the pair with `enabled` true.
3. `target_register.json` lists the target with `enabled` true.
4. The `eligibility` table of `target_register.json` carries an active row for
   the unit's target, the component's kind and the component's channel with
   `eligible` true. A pair the table rejects records `E_NOT_ELIGIBLE` and is not
   a unit.

The unit's pool is the component's `pool_id`. Its priority class is the
component's `priority_class`, unless addendum A names the component in its
override table, in which case the override is authoritative.

## 4. Stage 2, resolving toolchain and contract revisions

The toolchain revision of a unit is the string

    <toolchain_id>@<chain_revision>+<profile_id>@<profile_revision>

built as follows.

1. The toolchain is the active row of `target_overrides.jsonl` for the unit's
   target, kind and channel when one exists. When none exists the toolchain is
   the default for the kind: among the active `kind_defaults` rows of
   `toolchains.json` with `is_default` true for that kind, the one whose
   `toolchain_id` is bytewise greatest, and that chain must itself be an active
   row of `chains`.
2. `chain_revision` is that chain's `revision`.
3. The profile is the active `compiler_profiles.json` row for the unit's target,
   kind and channel; `profile_id` and `profile_revision` come from it.

The previous toolchain revision of a unit is the same string built from the
active `toolchain_history.csv` row for the previous release id, the unit's
target, kind and channel.

The contract revision of a unit is

    sha256(";".join("<interface_id>:<contract_revision>" for each required
           interface, in bytewise interface order))[:12]

where the required interfaces of a component are the interfaces for which
`interface_consumers.csv` carries an active row naming it as consumer with
`requirement` equal to `required`, and each revision comes from the active row
of `current_contracts.jsonl`. A component with no required interface has the
digest of the empty string. Optional consumption never enters the digest.

The previous contract revision is the same digest computed from
`previous_contracts.jsonl`.

## 5. Stage 3 and 4, invalidation

A unit carries a reason set. The direct reasons are:

- `absent_from_previous_release` when `previous_release_ledger.jsonl` has no
  active row for the unit. No other direct reason is recorded for such a unit,
  because there is nothing to compare it against.
- `source_changed` when the active `source_revisions.jsonl` revision differs
  from the ledger row's `source_revision`.
- `toolchain_changed` when the resolved toolchain revision differs from the
  previous one.
- `contract_changed` when the contract revision differs from the previous one.
- `published_artifact_missing` when the ledger row's `artifact_digest` has no
  active `published_artifact_index.jsonl` row with `retained` true. The
  exception `E_ARTIFACT_MISSING` is recorded.

The propagated reasons are:

- `dependency_rebuilt` when any required build dependency of the component has
  a unit for the same target that carries a reason. Optional dependencies
  propagate only on the targets section 2 rule 8 activates. A dependency with
  no unit for this target propagates nothing.
- `generated_interface_rebuilt` when the component consumes an interface, as a
  required or an optional consumer, whose contract revision differs from the
  previous one and whose generating unit exists for this target. An optional
  interface therefore invalidates its consumer without changing the contract
  digest.

Propagation is iterated until no reason set changes. A unit's reason set is
reported sorted and deduplicated. A unit with a reason set is dirty; a unit
with an empty reason set is reusable and its previous artifact is reused.

`generated_outputs.jsonl` declares the generated outputs of each interface. An
output regenerates when its row is active, `regenerate_on_contract_change` is
true and the interface's contract revision changed. A regeneration whose target
is not `supported` in `sdk_support_matrix.csv` does not regenerate and records
`E_SDK_UNSUPPORTED`.

## 6. Stage 6, cost

Addendum A section A1 defines the four ordered steps, A2 the ceiling rule.
The inputs are:

- `base_cost_ticks` from the component register.
- the platform fraction from the `platform_scaling` sheet of
  `capacity_workbook.xlsx`, read for the unit's target, kind and channel.
- the regeneration and cold cache fractions from the `cost_rules` sheet of the
  same workbook.
- whether each of those two steps applies to the unit's kind, channel and
  target, from `kind_cost_profiles.json`.
- the floor from `build_cost_rules.jsonl`, read for the unit's kind, channel and
  target.

Only dirty units have a cost. A reusable unit consumes no capacity.

## 7. Stage 7, capacity

Pool budgets and their conversion are addendum A section A3; the admission
order and the selection objective are section A4; cross pool prerequisites are
section A5. Which units a closure contains is settled here, by the definition
below. Where section A4 restates the closure in short form it names the
required build edge alone, and that shorter sentence does not narrow the two
edge kinds below.

The prerequisite closure of a candidate is the candidate together with every
dirty unit reachable from it, for the same target, through

- required build dependencies, and
- the generating unit of an interface the component consumes whose contract
  revision changed.

A closure may span several pools. It is admitted only when, for every pool it
draws on, the pool's remaining net budget covers the draw. Admission charges
each member to its own pool.

A publication prohibition does not remove a unit from a closure. A prohibited
unit is never a candidate in its own right, but when an admitted closure needs
it the unit is built, charged to its pool, and reported as
`built_not_published`. It never enters the deployment manifest. The
prohibitions are:

- a `prohibitions` row of `publication_policy.json` naming the component and
  target, recorded as `E_PROHIBITED`;
- a `publication_review` of `held` for the component, recorded as
  `E_REVIEW_HELD`;
- a channel marked `frozen` in `release_channels.toml`, recorded as
  `E_CHANNEL_FROZEN`.

A candidate deferred on its own order position is still admitted later if an
admitted closure includes it, and its deferral record is then dropped.

## 8. Stage 9, cycles

Cycle policy is addendum A section A6. A cycle is read on the graph of selected
units, where an edge runs from a required dependency to its dependent. The
governing group of a cycle is the active `cycle_groups.json` group whose member
set equals the set of components in the cycle and whose `applicability` row for
the cycle's target is active with `in_scope` true. A cycle with no governing
group, or one whose governing group is `blocking`, or one whose governing group
declares no break cost for any edge of the cycle, blocks its target: every unit
of the cycle leaves the release with `E_CYCLE_BLOCKING` and the target is
reported as blocked.

After cycle resolution, a selected unit whose closure has lost a member is
demoted to deferred with `E_PREREQ_DEFERRED`, and the demotion repeats until no
selected unit has an unselected closure member. Capacity released by a demotion
is not readmitted.

## 9. Stage 8 and 10, the schedule

The schedule covers every unit still selected, including the
`built_not_published` ones. Its edges are, in this order:

1. the surviving required dependency edges of the selected set;
2. the active `migration_first` rows of `deployment_constraints.jsonl`, in
   bytewise order of their three identifiers, each edge running from the
   migration unit to the blocked unit;
3. the active rows of `ordering_overrides.jsonl`, in bytewise `row_id` order,
   each edge running from `before_unit` to `after_unit`.

An edge from group 2 or 3 that would close a cycle is dropped and recorded as
`E_ORDER_IGNORED`. Sequence numbers start at 1 and the ready set order is
addendum A section A7.

## 10. Stage 11 and 12, compatibility and version selection

Addendum B is the authority. Version candidates come from
`component_versions.jsonl`, read under section 2, restricted to the versions
addendum B leaves `supported`. A component with no supported version records
`E_WITHDRAWN_VERSION`.

Selection runs per cluster of `version_precedence.json`, over the cluster
members that contribute at least one selected unit to this release. A pair of
versions is compatible only when `api_compatibility.jsonl` carries an active row
for the cluster, the two components and the two versions with `compatible`
true; a pair with no such row is incompatible. The selected combination is the
compatible combination with the smallest sum of `local_preference`, ties
settled by the bytewise sequence of versions in bytewise member order. A
cluster with no compatible combination is unresolved and records
`E_CLUSTER_UNRESOLVED`.

Every candidate combination whose preference sum is strictly smaller than the
selected one and which is not compatible is a rejected combination. For an
unresolved cluster every candidate combination is rejected.

## 11. Stage 13 and 14, the package

`artifact_register.md` lists every output file, its records and its keys, its
record order and its serialization. Those rules are part of this contract.

Membership states are:

- `included`: selected and publishable.
- `built_not_published`: selected but prohibited from publication.
- `reused`: not dirty; the previous artifact is reused.
- `deferred`: dirty, not prohibited, not selected.
- `excluded`: dirty and prohibited, and not needed by any admitted closure.
- `blocked`: removed by cycle policy.

The release decision is `blocked` when any target is blocked or any cluster is
unresolved; otherwise `deferred` when any mandatory component has a unit in
`deferred`, `blocked` or `excluded`; otherwise `publishable`.

## 12. Invariants

A package that breaks any of these is wrong whatever else it contains.

1. Every cost record names a unit of the build unit ledger, and only dirty units
   have cost records.
2. Every scheduled unit is selected, and every selected unit is scheduled
   exactly once.
3. Every required dependency edge between two scheduled units runs from the
   lower sequence number to the higher.
4. For every pool, consumed ticks equal the summed cost of its selected units
   and never exceed the net budget.
5. Every generated output in the deployment manifest carries the contract
   revision of its interface and the selected version of its producer.
6. Every reused unit has an empty reason set and an artifact digest that the
   artifact index retains.
7. A deferred or blocked unit never appears in the deployment manifest and never
   appears as a newly built artifact.
8. Every deployed version appears in the version selection and in the
   compatibility matrix.
9. Every cycle resolution appears in the schedule as a removed edge or as a
   blocked target, and in no other form.
10. The release decision is derived from the same final state as every other
    output.

## 13. Determinism

The same corpus must produce the same bytes. Nothing depends on the order rows
arrive in, on wall clock time, on the host, on any environment variable, or on
any network service. Floating point is not used anywhere in the derivation.

## 14. Stage 15, amortizing build cost across required consumers

Every selected unit that generates an interface output carries its build cost
for the components that depend on that interface. The cost is shared out in
whole ticks, under these rules.

1. A producer unit is a selected unit whose component is the
   `generated_sdk_component` of an active `generated_outputs.jsonl` row. The
   interface of that row is the interface it produces.
2. The consumers of that interface are the components for which
   `interface_consumers.csv` carries an active row with `requirement` equal to
   `required`. Optional consumption carries no cost.
3. A consumer takes a share only when it has a selected unit on the producer's
   target. A consumer with no selected unit on that target is left out and its
   share is not reassigned.
4. With `n` consumers taking a share and a producer cost of `c` ticks, the base
   share is `c // n` and the remainder is `c - n * (c // n)`. The remainder is
   handed out one tick each to the first consumers in bytewise `component_id`
   order, so the shares of a producer always sum back to `c`.
5. A producer whose cost is 0 still produces one record per consumer, each with
   a share of 0.
6. A producer with no consumer taking a share produces no record, and its cost
   stays where the cost breakdown put it.
7. `remainder_rank` is the 1 based position of the consumer in that bytewise
   order, and it is recorded whether or not that consumer drew a remainder
   tick.
