# Diagnosis of the retired planner

The retired planner (`legacy_planner.py` with `legacy_cost_helpers.py`) is kept
in the corpus for comparison only. Every entry below names a defect of that
planner that the corrected planner in `relplan.py` does not reproduce, together
with the rule of the handbook, addendum A (`rounding_precedence_addendum.pdf`)
or addendum B (`compatibility_window_notes.docx`) that the defect broke. All
rule numbers refer to `release_engineering_handbook.md` unless a letter
prefix names an addendum section.

1. **The four step cost arithmetic was collapsed into one multiplication.**
   `blended_cost` multiplied the base cost by every applicable fraction in a
   single expression and rounded once at the end, and it did the arithmetic in
   floating point with `int(value + 0.5)`. Rule broke: handbook section 6 with
   addendum A sections A1 and A2, which build the cost in four ordered steps,
   round each step up to a whole tick before the next step reads it, and forbid
   floating point anywhere. The corrected planner runs step 1 platform scaling,
   step 2 regeneration, step 3 cold cache and step 4 the kind minimum with
   `ceil(a/b) = (a + b - 1) // b`, all in integers, and reports every
   intermediate value.

2. **The kind minimum was never applied.** The retired planner never read
   `build_cost_rules.jsonl`, so a unit could be costed below the floor its kind,
   channel and target require. Rule broke: addendum A section A1 step 4, which
   sets `c4 = max(c3, minimum_cost_ticks)` and never lifts a zero cost unit.

3. **The wrong cost column was read.** The retired planner costed units from
   `legacy_cost_ticks`. Rule broke: handbook section 3 rule 1, which takes
   `base_cost_ticks` from the component register; section 2 rule 10 and the
   `legacy_cost_ticks` normalization case make the legacy column an input that
   never feeds planning.

4. **Costs were not derived from the profile the unit's kind, channel and
   target name.** The retired planner looked the regeneration surcharge and the
   cold cache multiplier up by rule name only and applied them from the reason
   text it happened to have. Rule broke: handbook section 6, which takes the
   two fractions from the `cost_rules` sheet and their applicability from
   `kind_cost_profiles.json` for the unit's kind, channel and target, and
   addendum A section A1, which makes step 2 depend on `contract_changed` or
   `generated_interface_rebuilt` and step 3 on `absent_from_previous_release`.

5. **Corrections were read by file position, not by revision.** The retired
   planner kept the last row it saw for a component, on the assumption that
   corrections are appended. Rule broke: handbook section 2 rule 6, where the
   row with the greater `revision_seq` wins and ties are settled by the
   bytewise greater `row_id`, applied to every shipped table.

6. **Superseded and inactive rows were applied.** The retired planner built its
   chain, profile, kind default, override and history tables without reading
   `status` or `state`. Rule broke: handbook section 2 rule 5, under which any
   row whose `status` or `state` column reads other than `active` is not
   applied.

7. **Identifiers were not normalized or validated.** The retired planner
   stripped padding but accepted lower case and other non canonical forms and
   recorded no exception for them. Rule broke: handbook section 2 rules 1 and
   2, which strip padding before matching, reject any identifier that is not in
   the canonical form of its register and record `E_ID_FORM`.

8. **Identifiers that name no row of their register were never detected.** The
   retired planner silently ignored components, targets, pools and interfaces
   that do not exist. Rule broke: handbook section 2 rule 9, which ignores the
   row and records `E_UNKNOWN_UNIT`, and for pools `E_UNKNOWN_POOL`, and
   section 3 rule 4, which records `E_NOT_ELIGIBLE` for the pair the eligibility
   table refuses.

9. **The eligibility table and the target register were never consulted.** The
   retired planner created a unit from the target matrix and the component
   register alone. Rule broke: handbook section 3 rules 2 to 4, which also
   require the target matrix row to be enabled, the target to be listed with
   `enabled` true in `target_register.json` and the eligibility table to accept
   the target, kind and channel.

10. **A tick field carrying a decimal point was truncated instead of
    refused.** The retired planner's `number()` truncated a decimal to its
    integer part and so accepted `41.5` as a tick count. Rule broke: handbook
    section 2 rule 4, under which such a row is ignored and `E_NON_INTEGER` is
    recorded, and addendum A section A2, which treats a fraction with
    denominator 0 as the same row defect.

11. **Milli tick fields were never converted.** The retired planner read
    `budget_value` and reservation fields as plain tick counts. Rule broke:
    handbook section 2 rule 7, which converts a field whose name ends `_millis`
    with `ceil(value / 1000)`.

12. **Pool budgets and reservations were misstated.** The retired planner took
    the superseded workbook budget rows and ignored every maintenance window,
    so its pool summaries did not reconcile against the workbook. Rule broke:
    addendum A section A3, which takes the active `pool_budgets` row with the
    highest `revision_seq`, converts a `milli_tick` budget with a ceiling
    division and nets the reservation of every active maintenance window
    naming the pool, never below 0. This is the "pool summary does not
    reconcile" symptom.

13. **The toolchain default was the last row seen, not the greatest.** The
    retired planner kept the last active `kind_defaults` row per kind, so on
    some targets it resolved a different chain than the declared default and
    rebuilt units that nothing had touched, on one target only. Rule broke:
    handbook section 4 rule 1, which names the bytewise greatest active
    `kind_defaults` row with `is_default` true for the kind, on condition that
    the chain is itself an active row of `chains`. This is the "untouched unit
    rebuilt on one target only" symptom.

14. **The contract digest covered optional consumption.** The retired planner
    built the digest over every interface a component consumes. Rule broke:
    handbook section 4, under which the required interfaces of a component
    alone enter the digest, taken in bytewise interface order from the active
    `current_contracts.jsonl` rows, so optional consumption never changes the
    digest.

15. **Every declared optional dependency was treated as live.** The retired
    planner propagated invalidation through optional build edges on every
    target. Rule broke: handbook section 2 rule 8, under which an optional build
    dependency applies to a target only when `optional_dependencies.jsonl`
    carries an active row for that dependent, dependency and target with
    `activated` true.

16. **Retention in the published artifact index was never checked.** The
    retired planner never read `published_artifact_index.jsonl`, so a unit whose
    previous artifact had been revoked or was absent was reused anyway. Rule
    broke: handbook section 5, which adds `published_artifact_missing` and
    records `E_ARTIFACT_MISSING`, and section 2 rule 6, under which an artifact
    index entry revokes retention. The corrected planner reuses an artifact only
    when the index retains it and reports the digest that justifies the reuse.

17. **Invalidation was not propagated to a fixed point and one reason was
    missing.** The retired planner ran three passes over the build edges and
    never propagated through a rebuilt generated interface. Rule broke:
    handbook section 5, which iterates propagation until no reason set changes
    and adds `generated_interface_rebuilt` for a consumed interface whose
    contract revision changed and whose generating unit exists for the target.

18. **Publication review, channel freeze and the prohibition table were not
    enforced.** The retired planner knew one hard coded prohibition rule, put
    prohibited units on the deferred list and shipped units whose review was
    held. Rule broke: handbook section 7 and addendum B section B2, under which
    a prohibited, review held or frozen channel unit is never a build candidate
    in its own right, is built and charged when an admitted closure needs it,
    is reported `built_not_published` and never enters the deployment manifest.
    This is the "unit published although its review is held" symptom.

19. **Admission ranked single units by priority and ignored closures.** The
    retired planner sorted the dirty units by priority class and admitted them
    one at a time until the pool ran out, and it charged each unit to its own
    pool only. Rule broke: addendum A sections A4 and A5 and handbook section 7,
    which order pools bytewise, order candidates by
    `(priority_class, closure_cost, unit_id)`, admit a candidate only with its
    whole prerequisite closure, check the draw against the remaining net budget
    of every pool the closure draws on, defer under `E_CAPACITY` and demote a
    selected unit whose prerequisite was not selected under `E_PREREQ_DEFERRED`.
    This is the "deferral with no stated cause" symptom.

20. **Cycle policy was read from the wrong edge and the wrong scope.** The
    retired planner removed the bytewise first key of the group's `break_costs`
    on the first target it found and ignored both the group policy and the
    applicability rows. Rule broke: addendum A section A6 and handbook section
    8, under which the edge minimising `(break_cost, source, destination)` is
    removed, a cycle whose governing group is blocking, out of scope for the
    target or without a declared break cost blocks the target under
    `E_CYCLE_BLOCKING`, and the units of the cycle leave the release. This is
    the "cycle broken at a different edge than the group names" symptom.

21. **The schedule ignored the migration and ordering rules.** The retired
    planner built the schedule from surviving required dependency edges alone,
    dropped nothing that would close a cycle and ordered the ready set by unit
    id alone. Rule broke: handbook section 9, which adds the active
    `migration_first` rows in bytewise order of their three identifiers and the
    active `ordering_overrides` rows in bytewise `row_id` order, records
    `E_ORDER_IGNORED` for an edge that would close a cycle and numbers the
    sequence from the ready set order of addendum A section A7.

22. **Versions were chosen per component, not per cluster.** The retired
    planner took each component's most preferred version that was not withdrawn
    and never read `api_compatibility.jsonl`. Rule broke: handbook section 10
    and addendum B, which select per cluster the compatible combination with
    the smallest sum of `local_preference`, settle ties by the bytewise sequence
    of versions in bytewise member order, report every locally cheaper
    combination that compatibility rejects, and record `E_CLUSTER_UNRESOLVED`
    for a cluster with no compatible combination. This is the "client version
    rejected by its own interface" symptom.

23. **Generated client outputs were never planned or published.** The retired
    planner ignored `generated_outputs.jsonl` and `sdk_support_matrix.csv`
    entirely. Rule broke: handbook section 5, under which an output regenerates
    when its row is active, `regenerate_on_contract_change` is true and the
    interface's contract revision changed, a regeneration whose target is not
    `supported` does not regenerate and records `E_SDK_UNSUPPORTED`, and
    section 14, which shares the producer's cost over its required consumers.
    This is the "generated client missing from the candidate" symptom.

24. **The release decision was not derived from the release state.** The
    retired planner decided `publishable` whenever nothing was on its deferred
    list. Rule broke: handbook section 11, under which the decision is `blocked`
    when any target is blocked or any cluster is unresolved, otherwise
    `deferred` when any mandatory component has a unit in `deferred`, `blocked`
    or `excluded`, and otherwise `publishable`, and section 12 rule 10, which
    requires the decision to be derived from the same final state as every
    other output.

25. **The output package itself was not the registered package.** The retired
    planner wrote a single comparison report and none of the registered
    artifacts, so no release unit ledger, provenance, cache reuse, capacity,
    compatibility, migration or audit record existed to be checked. Rule broke:
    handbook section 11 with `artifact_register.md`, which fixes the records,
    keys, record order and serialization of every output file, and section 12,
    whose invariants can only be checked against those artifacts.

26. **Observed wall time and legacy columns fed the build.** The retired
    planner read timing and legacy columns as planning inputs. Rule broke:
    handbook section 0, under which `previous_build_timings.csv` is reporting
    only and every column whose name begins `legacy_` or `observed_` never
    feeds planning.
