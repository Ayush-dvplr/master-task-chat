# Diagnosis of the retired planner, release R-NEXT

Each entry below is a defect of `legacy_planner.py` / `legacy_cost_helpers.py`
(as confirmed by `legacy_notes.md` and `retired_run_report.json`) that this
build corrects, with the rule it broke. Rule references are to the release
engineering handbook (H), addendum A, `rounding_precedence_addendum.pdf` (A),
addendum B, `compatibility_window_notes.docx` (B), and the artifact register
(R).

1. **It priced units from `legacy_cost_ticks`.** The register's base cost is
   `base_cost_ticks`; every column whose name begins `legacy_` or `observed_`
   is reporting only and never feeds planning (H preamble, H §6). The corrected
   planner reads `base_cost_ticks` and never reads `legacy_cost_ticks` or
   `previous_build_timings.csv`.

2. **It blended every cost fraction into one floating point multiplication and
   rounded once at the end** (`blended_cost`). Cost is four ordered steps, each
   rounding up to a whole tick before the next step reads it, and collapsing
   them is explicitly not the documented arithmetic (A1, A2). Floating point is
   not used anywhere in the derivation (H §13). The corrected planner uses
   `ceil(a/b) = (a+b-1)//b` on integers at every step and reports
   `after_platform`, `after_regeneration` and `after_cold_cache`.

3. **It never applied the kind minimum.** Step 4 of the scaling order takes the
   floor `minimum_cost_ticks` of `build_cost_rules.jsonl` for the unit's kind,
   channel and target, and it never lifts a unit whose `base_cost_ticks` is 0
   (A1 step 4). Both halves of that rule are now implemented.

4. **It applied the regeneration surcharge on `contract_changed` alone.** Step 2
   applies when the kind takes the surcharge and the unit carries
   `contract_changed` *or* `generated_interface_rebuilt` (A1 step 2).

5. **It read pool budgets as plain numbers.** A budget whose `scale_unit` reads
   `milli_tick` converts with `ceil(budget_value/1000)`, the winning row is the
   active row with the highest `revision_seq`, and the net budget subtracts the
   reservation of every active maintenance window naming the pool, each window
   converted by its own field name and never below 0 (A3). This is the cause of
   the "pool summary does not reconcile against the workbook" symptom; the pool
   summary now reports gross, reserved, net, consumed and remaining ticks per
   pool and consumed never exceeds net (H §12.4).

6. **It admitted units one at a time by `(priority_class, unit_id)` without
   pricing the closure.** The candidate order inside a pool is
   `(priority_class, closure_cost, unit_id)` with `closure_cost` the summed cost
   of the candidate's own prerequisite closure counting only members not already
   selected, pools are admitted in bytewise `pool_id` order, and a candidate is
   admitted only with its whole closure; ranking units one at a time by priority
   is explicitly not the documented objective (A4). Closures are now priced,
   admitted whole, charged to each member's own pool, and a closure exactly
   equal to the remaining net budget fits while one tick larger does not.

7. **Its closure had no definition at all**, so cross pool prerequisites were
   never judged. The closure is the candidate plus every dirty unit of the same
   target reachable through required build edges *and* through the generating
   unit of a consumed interface whose contract revision changed (H §7, A4, A5);
   a selected unit that loses a closure member is demoted under
   `E_PREREQ_DEFERRED` and the released capacity is not readmitted (A5, H §8).

8. **It never recorded a reason code for anything it dropped.** Every unit that
   is not built now carries a traceable code (`E_CAPACITY`,
   `E_PREREQ_DEFERRED`, `E_CYCLE_BLOCKING`, `E_PROHIBITED`, `E_REVIEW_HELD`,
   `E_CHANNEL_FROZEN`) with the subject the audit registry fixes (R
   `audit_exceptions.jsonl`, H §7, H §8). This answers the "deferral with no
   stated cause" symptom.

9. **It kept the last register row it saw for each component.** A row whose
   `status` is anything other than `active` is not applied, and two active rows
   with the same key are resolved by the greater `revision_seq`, then by the
   bytewise greater `row_id` (H §2 rules 5 and 6). That resolution is now
   applied to every shipped table, including `target_overrides.jsonl`,
   `toolchain_history.csv` and the addendum tables.

10. **It accepted identifiers that are not in canonical form.** `c-0004` and its
    like make their row invalid: the row is ignored and `E_ID_FORM` is recorded
    against the stripped text (H §2 rule 2). Padding is stripped before
    matching (H §2 rule 1), which the retired planner only did for two tables.

11. **Its `number()` helper truncated decimals** (`41.5` became `41`). A tick
    field carrying a decimal point is not an integer: the row is ignored and
    `E_NON_INTEGER` is recorded (H §2 rule 4, A2 for a zero denominator).
    Underscore digit grouping is still an ordinary integer (H §2 rule 3).

12. **It never checked identifiers against their registers.** An identifier that
    names no row of its register is ignored under `E_UNKNOWN_UNIT`, and a pool
    that names no row of the pool register under `E_UNKNOWN_POOL` - once per
    offending row, so a ghost pool named by both a budget row and a maintenance
    window is recorded twice (H §2 rule 9, R). The retired planner silently
    carried ghost pools into its budget table.

13. **It ignored eligibility and the target register's `enabled` flag.** A unit
    exists only when the target matrix row is active and enabled, the target is
    listed as enabled, and the eligibility table carries an active row for the
    target, kind and channel with `eligible` true; a refused pair records
    `E_NOT_ELIGIBLE` and is not a unit (H §3).

14. **It treated every declared optional build dependency as live.** An optional
    dependency applies to a target only when `optional_dependencies.jsonl`
    carries an active row for that dependent, dependency and target with
    `activated` true (H §2 rule 8, H §5). This is the cause of the "untouched
    unit rebuilt on one target only" symptom: invalidation now propagates
    through required edges always and through optional edges only on the
    activated targets.

15. **It built the contract digest over every consumed interface and did not
    truncate it.** The contract revision is
    `sha256(";".join("<interface_id>:<contract_revision>"))[:12]` over the
    *required* interfaces in bytewise order; optional consumption never enters
    the digest, and a component with no required interface takes the digest of
    the empty string (H §4).

16. **It resolved the default toolchain by the last `kind_defaults` row it saw**
    and ignored `status` on both `kind_defaults` and `chains`. The default is
    the bytewise greatest `toolchain_id` among the active default rows for the
    kind, and that chain must itself be an active row of `chains` (H §4 rule 1).
    The previous toolchain revision is read from the active
    `toolchain_history.csv` row for the *previous release id* (H §4), which the
    retired planner never matched on.

17. **It never consulted the published artifact index.** A unit whose ledger
    `artifact_digest` has no active index row with `retained` true carries
    `published_artifact_missing` and records `E_ARTIFACT_MISSING`, and an index
    row revokes retention through the same-key precedence rule (H §5, H §2 rule
    6). Reuse is now justified by a digest the index still retains (H §12.6),
    reported in `cache_reuse_manifest.jsonl`.

18. **It stopped propagating after three passes.** Propagation is iterated until
    no reason set changes, and a unit's reason set is reported sorted and
    deduplicated with direct causes kept distinguishable from propagated ones
    (H §5).

19. **It had no notion of generated interface output.** A unit carries
    `generated_interface_rebuilt` when it consumes, as a required *or* an
    optional consumer, an interface whose contract revision changed and whose
    generating unit exists for the target; an output regenerates only when its
    row is active, `regenerate_on_contract_change` is true and the contract
    changed, and a regeneration the support matrix refuses records
    `E_SDK_UNSUPPORTED` as `<interface_id>@<unit_id>` (H §5, R). This answers
    the "generated client missing from the candidate" symptom: the plan and the
    generated client manifest are now emitted, and every entry carries the
    contract revision of its interface and the selected version of its producer
    (H §12.5).

20. **It ignored the priority class overrides of addendum A section A8.** A
    component the override table names takes the `priority_class` of its active
    row with the highest `revision_seq`; a superseded row is not applied, a row
    naming an absent component is ignored under `E_UNKNOWN_UNIT` and a row whose
    identifier is not canonical under `E_ID_FORM` (A8, H §3). The inventory now
    reports `priority_overridden` per unit.

21. **It published units it was forbidden to publish.** A prohibitions row, a
    `publication_review` of `held` and a frozen channel each prohibit
    publication, outrank capacity priority and keep the unit out of the
    deployment manifest; a prohibited unit is never a candidate in its own
    right, but when an admitted closure needs it the unit is built, charged to
    its pool and reported as `built_not_published` (H §7, B2). This answers the
    "unit published although its review is held" symptom.

22. **It broke a cycle at the lexicographically first edge name in the group.**
    A live cycle in a breakable group loses the edge minimising
    `(break_cost, source, destination)`, an edge with no declared break cost is
    not removable, and the cycle is read on the graph of selected units with the
    governing group being the active group whose member set *equals* the set of
    components in the cycle and whose applicability row for that target is
    active with `in_scope` true (A6, H §8). The retired planner also matched
    groups by walking the declared member ring, ignored `applicability` and
    `status`, and removed the edge on every target at once rather than on the
    target the cycle is live on. This answers the "cycle broken at a different
    edge than the group names" symptom.

23. **It never blocked anything.** A cycle with no governing group, or one whose
    governing group is `blocking`, or one that declares no break cost for any of
    its edges, blocks its target: every unit of the cycle leaves the release
    under `E_CYCLE_BLOCKING` and the target is reported as blocked (H §8, A6).

24. **It chose each component's most preferred version on its own.** Selection
    runs per cluster of `version_precedence.json` over the members that
    contribute at least one selected unit; a pair is compatible only when
    `api_compatibility.jsonl` carries an active row for the cluster, the two
    components and the two versions with `compatible` true, a pair with no such
    row is incompatible, and the selected combination is the compatible
    combination with the smallest sum of `local_preference`, ties settled by the
    bytewise sequence of versions in bytewise member order (H §10, B). This
    answers the "client version rejected by its own interface" symptom. Every
    locally cheaper combination that compatibility rejects is now reported, and
    a cluster with no compatible combination is unresolved under
    `E_CLUSTER_UNRESOLVED`.

25. **It read the window table but ignored its `state` and `revision_seq`
    columns**, so superseded window rows and rows naming components outside the
    register were applied. A withdrawn version is not a candidate whatever its
    local preference, a superseded row is not applied, and a row naming an
    unregistered component is ignored under `E_UNKNOWN_UNIT`; a component with
    no supported version records `E_WITHDRAWN_VERSION` (B, B1, H §10).

26. **Its schedule ignored the schedule rules.** The edges are the surviving
    required dependency edges of the selected set, then the active
    `migration_first` rows of `deployment_constraints.jsonl` in bytewise order
    of their three identifiers, then the active rows of
    `ordering_overrides.jsonl` in bytewise `row_id` order; an edge of the second
    or third group that would close a cycle is dropped and recorded as
    `E_ORDER_IGNORED`; the ready set order is `(priority_class, unit_id)` and
    sequence numbers start at 1 (H §9, A7). The retired planner ordered the
    ready set by `unit_id` alone, dropped both constraint tables, and left
    `built_not_published` units out of the order.

27. **Its decision rule was "deferred if anything was deferred".** The decision
    is `blocked` when any target is blocked or any cluster is unresolved,
    otherwise `deferred` when any mandatory component has a unit in `deferred`,
    `blocked` or `excluded`, otherwise `publishable`, and it is derived from the
    same final state as every other output (H §11, H §12.10).

28. **It never shared a generating unit's cost across its required consumers.**
    The cost is shared in whole ticks: base share `c // n`, remainder handed out
    one tick each to the first consumers in bytewise `component_id` order so the
    shares sum back to `c`; a consumer with no selected unit on the producer's
    target is left out and its share is not reassigned; a zero cost producer
    still produces one record per consumer; `remainder_rank` is recorded whether
    or not the consumer drew a remainder tick (H §14).

29. **Its output was one ad hoc report.** The package, its records, its keys,
    its record order and its serialization are fixed by the artifact register,
    which is part of the handbook contract (H §11, R). All 28 artifacts are now
    written with keys sorted bytewise, no float anywhere, and the record order
    the register states.

30. **It was order dependent.** `defaults`, `overrides`, `history` and the
    per-target loops all kept whatever row arrived last, so the same corpus in
    another row order produced another candidate. The same corpus must produce
    the same bytes, and nothing may depend on row order, wall clock, host,
    environment or network (H §13). Every table is now resolved by the
    same-key precedence rule and every iteration runs over a sorted key.
