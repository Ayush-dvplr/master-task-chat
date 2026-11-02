# TRUTH.md - f3381a1c-4074-52d0-9259-183d66492268

## Defect

The corpus in `/app/data` describes one release train for release `R-NEXT`: 240
components, six deployment targets, 934 eligible release units, a previous
release ledger, a published artifact index, a dependency graph with declared
cycle groups, five worker pools and a compatibility model over 73 version
clusters. The release engineering handbook and its two addenda state every rule
needed to plan the release. The planner that actually produced the last
candidate, `legacy_planner.py`, is shipped beside its helpers and its last
report, and its derivations are wrong in fourteen separate ways. The work is to
write a planner that derives the package the handbook describes, from any corpus
of this shape.

What is broken, and where the difficulty sits:

1. (focal) Cost scaling. The retired planner multiplies the base cost by every
   applicable fraction in one float expression and rounds once at the end.
   Addendum A section A1 states four ordered steps with a ceiling applied after
   each step, and the two orders disagree on hundreds of units. The surcharge
   fractions themselves live only in the `cost_rules` sheet of the binary
   workbook, where the active rows are 17 over 10 and 23 over 20 and the
   superseded rows are 11 over 10 and 13 over 10.
2. (focal) Capacity admission. The retired planner ranks dirty units one at a
   time by priority class. Addendum A section A4 prices the whole prerequisite
   closure of a candidate, admits it only when every pool the closure draws on
   can cover its own share, and leaves the closure members free to be admitted
   later on their own order position. Ranking units alone admits a different
   set, and the difference cascades into the schedule, the manifest and the
   decision.
3. (focal) Pool budgets. The workbook carries each pool's budget with a
   `scale_unit`, and two of the five pools are stated in `milli_tick`. Addendum
   A section A3 converts those with a ceiling division by 1000 and then
   subtracts every active maintenance window reservation, each window converted
   by its own field name. The retired planner reads the budget as a plain
   number and ignores the windows.
4. (focal) Version selection. The retired planner takes each component's own
   most preferred version that is not withdrawn. Addendum B selects, per
   cluster, the compatible combination with the smallest sum of
   `local_preference`, and cluster `CL-900` has no compatible combination at
   all, which blocks the release.
5. (drift) Reading rows. An experienced reader takes the last row of a table as
   the correction. Handbook section 2 rule 6 settles duplicate keys by the
   greater `revision_seq` and then by the bytewise greater `row_id`, and rule 5
   drops every row whose status reads `superseded`. The retired planner keeps
   the last row it sees, which is how it ends up on the superseded surcharges
   and the halved budgets.
6. (drift) Cost input. The component register carries a `legacy_cost_ticks`
   column beside `base_cost_ticks`, and the retired planner costs from it. The
   handbook preamble excludes every `legacy_` and `observed_` column from
   planning, so `previous_build_timings.csv` and the retired report are
   reporting surfaces and nothing more.
7. (drift) Prohibitions. A publication prohibition reads like an exclusion.
   Handbook section 7 keeps a prohibited unit out of the deployment manifest but
   still builds it, charged to its pool, when an admitted closure needs it, and
   reports it as `built_not_published`.
8. (trap) The priority class of 120 components is overridden only inside the
   PDF addendum's table, 96 of them to a class the register does not carry,
   which a reader who never opens the binary document cannot see. The override changes the admission order and therefore the
   admitted set.
9. (trap) Pool `P-ZETA` holds four units priced so that one closure equals the
   remaining net budget exactly and the next exceeds it by exactly one tick. An
   implementation that compares with the wrong strictness gets both wrong.
10. (trap) An optional interface never enters the contract digest, yet a change
    to its contract revision still invalidates its consumer through the
    generated output rule of handbook section 5. The two rules pull in opposite
    directions on the same row.
11. (trap) Twelve rows of `published_artifact_index.jsonl` revoke retention on a
    digest that an earlier row retains, and the revoking row wins on `row_id`
    alone. Those units are rebuilt although nothing about their source,
    toolchain or contract changed.
12. (trap) Two active applicability rows take a breakable cycle group out of
    scope on one target, and ten superseded rows beside them change nothing. A
    cycle with no governing in scope group blocks that target rather than losing
    an edge, so a group whose policy reads `breakable` still blocks, and four
    targets end up blocked in all.
13. (trap) A unit whose `base_cost_ticks` is 0 keeps cost 0: the kind minimum of
    step four never lifts it, and it is still a build unit that has to be
    admitted and scheduled.
14. (trap) `toolchain_history.csv` is the only previous side of the toolchain
    delta, and five of its rows carry a drifted revision at a higher
    `revision_seq`. A planner that composes the two sides differently reports
    every unit as toolchain changed.

The reference implementation in `solution/solve.py` is a single standard library
program of about 1330 lines. It reads the corpus (CSV, TSV, JSONL, JSON, TOML,
INI, XLSX, DOCX and PDF) with its own readers, derives the fourteen stages in
order, and writes the 28 package files plus nothing else. `solution/solve.sh`
copies it to `/app/out/relplan.py`, runs it over `/app/data`, writes the
diagnosis document and then re-reads the package to confirm the pool arithmetic
and the schedule count before exiting.

Out of bounds: no network access, no third party package, no floating point in
any derivation, no write anywhere under `/app/data`, and no dependence on the
order rows arrive in. The hidden corpora are the same shape as the shipped one,
so a planner tied to these particular identifiers, pool names or figures earns
nothing from them.

## Load-bearing work

The graded deliverables are the 29 declared artifacts: the planner itself at
`/app/out/relplan.py`, the 27 package files, and `/app/out/diagnosis.md`.

Per deliverable contract:

- `normalized_inventory.jsonl`, `revision_delta.jsonl`,
  `toolchain_resolution.jsonl`, `contract_delta.jsonl`,
  `invalidation_reasons.jsonl`: one record per unit in bytewise unit order, with
  both sides of every delta and the sorted deduplicated reason set.
- `invalidation_closure.jsonl`, `generated_output_plan.jsonl`,
  `build_unit_ledger.jsonl`: the dirty set, the regeneration plan per interface
  and target, and the canonical ledger that every later stage keys off.
- `build_cost_breakdown.jsonl`: every intermediate tick value of the four cost
  steps for every dirty unit, so a reader can audit the rounding placement.
- `capacity_allocation.jsonl`, `deferred_units.jsonl`,
  `worker_pool_summary.json`: the admitted set with the candidate whose closure
  carried each member, the deferral codes, and the gross, reserved, net,
  consumed and remaining ticks per pool.
- `dependency_schedule.jsonl`, `cycle_resolution.jsonl`: one sequence number per
  scheduled unit with the surviving prerequisite edges, and one record per
  resolved cycle with the removed edge and its break cost.
- `compatibility_matrix.jsonl`, `rejected_combinations.jsonl`,
  `version_selection.jsonl`: the selected combination per cluster, every locally
  cheaper combination compatibility rejects, and the pairwise matrix.
- `release_membership.jsonl`, `deployment_manifest.json`,
  `generated_sdk_manifest.jsonl`, `migration_order.jsonl`: the six membership
  states, the publishable composition, the regenerated clients with their
  producer versions, and the migration ordering.
- `artifact_provenance.jsonl`, `cache_reuse_manifest.jsonl`,
  `release_delta.json`, `audit_exceptions.jsonl`, `release_decision.json`,
  `conformance_summary.csv`: lineage, justified reuse, the delta against the
  previous release, every exception with its registry code and the subject the
  artifact register fixes for that code, and the decision.
- `diagnosis.md`: one numbered entry per corrected defect, each naming the rule
  it broke.

## Verification

`tests/test.sh` hardens the verifier and hands the whole of `/tests` to
rewardkit, which scores the deterministic channel in `tests/test_output.py` and
the judged channel in `tests/judge.toml` and combines them at half weight each
through `tests/reward.toml`.

Channel A carries 39 checks: 34 positive checks summing to a positive total of
138, and 5 negative detectors summing to 19 in absolute value. Twenty nine
positive checks read the delivered package, either recomputing an invariant from
the artifacts themselves or comparing a projection digest against a constant
derived from the shipped corpus, four of them covering the amortization stage.
Five positive checks re-execute the delivered
`relplan.py` as an unprivileged user against two corpora embedded in the
verifier: the same release state with every row delivered in a different order,
which must reproduce the delivered package byte for byte, and a revised corpus
with different revisions, workbook figures, policy rows and compatibility
records, which must match the revised projection in invalidation, cost and
capacity, schedule and cycles, and version selection and decision.

The negative detectors are `negative_hardcoded_sample_answers` (the program
carries the final figures rather than deriving them),
`negative_reads_grader_paths` (the program reaches for the grading or log
directories), `negative_retired_budgets_copied` (the pool summary repeats the
retired planner budgets), `negative_float_in_outputs` (an artifact carries a
float where the register states integers) and
`negative_withheld_unit_published` (a deferred, blocked, excluded or
`built_not_published` unit appears in the deployment manifest).

Channel B carries 32 judged criteria, 28 positive summing to 90 and 4 negative
summing to 12 in absolute value. Ten of the positive criteria require the agent
to recompute a figure outside its own planner and compare the two: the surcharge
step, the priority class, the withdrawn window states, the `P-ZETA` admission
boundary, duplicate row resolution, the previous toolchain composition, the
required only contract digest, retention revocation, out of scope applicability
and the publication prohibition. The rest cover the `milli_tick` conversion, the
step rounding order, closure priced admission, the optional interface
invalidation, the cycle break tuple, the cluster version conflict, the retired
planner comparison, the rounding, capacity and compatibility vectors, the
normalization cases, a reordered corpus rerun, the audit code registry, and the
instruction's own constraints.
One further criterion judges the quality of the planner the agent writes, and
four judge whether the agent verified its own work: against the capacity
vectors, the compatibility vectors, a reordered corpus and the audit code
registry. The
four negative criteria fire on the `legacy_cost_ticks` column, per component
version choice, a reproducibility claim the agent's own last comparison
contradicts, and an edit to the shipped corpus. The retired pool budgets are left to the test channel alone, so no
single mistake is priced in both channels.

Measured scores for the test channel: the reference implementation reads
1.000 and an empty run reads 0.000. A forged package, right filenames and
empty bodies, reads 0.008. A solver that skips the amortization stage and is
otherwise correct reads 0.790, so one missing stage of fifteen costs about one
stage's worth. Earlier single-defect figures were measured against a 120 point
channel and are not comparable to the current 128 point one.

## Root cause

**One ledger, many consumers.** Every stage after the build unit ledger keys off
the identity and the state that the ledger assigns. A single wrong reason set
moves a unit between dirty and reusable, which moves its cost into or out of a
pool, which moves the admission boundary, which moves the schedule, which moves
the manifest and finally the decision. The defects are individually small and
collectively total, which is why a package can look plausible file by file and
still disagree with itself.

**Rounding placement is semantics, not style.** Ceiling after each step and
ceiling once at the end are different functions. The handbook fixes the order
because the release budget is spent in whole ticks and a planner that rounds
late spends ticks it does not have.

**Admission order follows addendum A4 literally.** The candidate order inside a
pool is `(priority_class, closure_cost, unit_id)`, and `closure_cost` counts
only closure members not already selected, so it is recomputed per pool rather
than fixed once before admission. Selecting units in an earlier pool therefore
changes the order in a later one.

**Local optimality is not global feasibility.** A unit that deserves its place
by priority can be infeasible once its prerequisites are priced, and a version
that is locally preferred can be rejected by the cluster it belongs to. Both
traps reward the same wrong instinct: decide per item, then aggregate.

**Authority is layered and stated.** The handbook, the PDF addendum, the DOCX
addendum and the artifact register each own named rules, and the retired planner
and its report own none. A reader who treats the shipped code as a specification
inherits all fourteen defects.

## Solution shape

1. Read the handbook, both addenda and the artifact register, and build the
   normalization layer first: padding, canonical identifier form, underscore
   grouping, decimal rejection, status filtering, duplicate resolution by
   `revision_seq` then `row_id`, and the `_millis` conversion.
2. Build the unit set from the register, the target matrix, the target register
   and the eligibility table, recording `E_NOT_ELIGIBLE` where the table
   refuses a kind on a channel.
3. Compose the toolchain revision from the override or the bytewise greatest
   default chain plus the profile, and the previous one from the history rows of
   the previous release. Build the contract digest over required consumption
   only, on both sides.
4. Derive the direct reasons, then iterate the dependency and generated
   interface propagation to a fixed point, honouring optional activation per
   target.
5. Cost every dirty unit in four ceiling steps from the workbook fractions, the
   kind profile flags and the kind minimum, leaving a zero base cost at zero.
6. Convert the pool budgets, subtract the window reservations, read the priority
   overrides out of the PDF, and admit prerequisite closures pool by pool in
   bytewise pool order.
7. Resolve cycles on the selected graph under the group policy and the
   applicability table, then demote any selected unit whose closure lost a
   member.
8. Schedule with the surviving edges plus the migration constraints and the
   ordering overrides, dropping any added edge that would close a cycle.
9. Select versions per cluster over the supported window, record the rejected
   combinations, assemble the manifests and the provenance, and derive the
   decision from the same final state.
10. Share each selected generating unit's cost across the components that
    require its interface, in whole ticks, handing the remainder to the
    bytewise first consumers so the shares add back to the cost.

## Ordered plan

1. Open the handbook, both addenda and the artifact register before anything
   else, and note which rule each authority owns (criteria R1 to R5, R23).
2. Run the retired planner and diff its report against the handbook to locate
   the defects (R17).
3. Implement the normalization layer and check it against
   `normalization_cases.jsonl` (R8, R24).
4. Implement the toolchain and contract resolution and confirm that twenty one
   units come out toolchain changed (R9, R10).
5. Implement invalidation, including the optional interface rule and the
   retention revocation (R11, R12).
6. Implement the four cost steps and check them against
   `validation_vectors_rounding.jsonl` (R5, R18).
7. Implement budget conversion, window reservation and closure priced admission,
   and confirm the `P-ZETA` boundary (R2, R6, R7).
8. Implement cycle resolution and the applicability rule (R13, R14).
9. Implement version selection per cluster and confirm `CL-900` is unresolved
   (R4, R15).
10. Write the package, rerun the planner over the shipped corpus and compare the
    two outputs byte for byte (R19).
11. Write the diagnosis document with one entry per corrected defect (R21).

## Pitfalls

- Costing from `legacy_cost_ticks`, or from the retired report, fails
  `cost_steps_rounded_in_order` and fires the judged criterion `R26`.
- One combined multiplication with a single final rounding fails
  `cost_steps_rounded_in_order` and every downstream admission check.
- Taking the last row of a table fails `pool_budgets_converted` through the
  superseded budget rows, and those rows equal the retired figures, so it also
  fires `negative_retired_budgets_copied`.
- Reading the budget without the `milli_tick` conversion fails
  `pool_budgets_converted` and fires `negative_retired_budgets_copied` when the
  retired figures are adopted wholesale.
- Ranking dirty units one at a time fails `closure_admission_exact`,
  `deferral_codes_exact` and `schedule_order_exact`.
- Never opening the PDF fails `priority_overrides_applied`.
- Never opening the DOCX fails `version_selection_exact`.
- Choosing versions per component fails `version_selection_exact` and
  `rejected_combinations_exact` and fires `R27`.
- Treating a prohibited unit as excluded outright fails
  `closure_admission_exact` and `deployment_manifest_exact`.
- Publishing a deferred or blocked unit fires
  `negative_withheld_unit_published`.
- Emitting a float anywhere fires `negative_float_in_outputs`.
- Fixing the shipped answers in the source fires
  `negative_hardcoded_sample_answers` and fails the revised corpus checks.

## Provenance

```yaml
uuid: f3381a1c-4074-52d0-9259-183d66492268
instance_id: f3381a1c-4074-52d0-9259-183d66492268
task_name: terminal-bench/f3381a1c-4074-52d0-9259-183d66492268
fix_patch_sha256: 52062586c0efb38c6eeadca5a7f4b1fd0aff65bfc371498d78051b7de75a49e0
solve_py_sha256: f78a944ed9a54d64e750a02c411a91aee912947f1d3d61263d92aedb72602c1f
language: python
```
