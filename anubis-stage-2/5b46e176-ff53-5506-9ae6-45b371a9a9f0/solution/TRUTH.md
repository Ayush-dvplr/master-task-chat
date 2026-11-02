# TRUTH.md - 5b46e176-ff53-5506-9ae6-45b371a9a9f0

## Defect

Nothing in this task is broken. What is missing is knowledge. The interchange
ships a complete written specification of how an epoch clears, across nine
rulebooks, an invariant statement and an artifact schema, and it ships the
registers of one epoch that has to be cleared. Seven properties of the
platform were never written into those rulebooks, and the only thing that
pins them is a small epoch the interchange already cleared and published the
figures for. The solver has to recover the seven properties from that
calibration slice, implement the whole specification, and produce a mutually
consistent set of artifacts whose conservation residuals are zero.

1. (focal) The seven withheld properties are the order the four rate
   adjustments compose in, the quantity the shortfall levy is a share of, the
   grid step, the midpoint convention, the reach of a reversal record, the cap
   release order and the fault window convention. Their candidate sets
   multiply out to 122880 readings and exactly one of them reproduces every
   published calibration figure. A reading recovered from fewer than all the
   published figures is under determined, because every property changes at
   least one figure and several change only one.
   Defeats `recovered_properties_match_calibration`.
2. (focal) The suspension states are mutually dependent and have to be driven
   to a fixpoint, not settled in one pass. A gate over its allowance withdraws
   its taps, which raises its own burden; a zone whose working gate count falls
   under its validation floor suspends every gate it owns; a provisional zone
   follows any unvalidated sibling of its operator; an operator all of whose
   zones are unvalidated stands down. In the shipped epoch two gates go over
   their allowance, which takes one zone under its floor, which drags a
   provisional sibling with it, which suspends two more gates. Two zones leave
   scope as a result. Defeats `suspension_fixpoint_matches_reference`.
3. (focal) The netting layer cancels cycles out of the obligation graph in a
   canonical cycle order, shortest first and then lexicographically from the
   smallest operator in the cycle. The shipped epoch cancels three two node
   cycles and then one genuine three node cycle, so an implementation that
   only offsets mutual pairs settles the first three and then stops with a
   graph that still has a cycle in it. Defeats
   `netting_cycle_cancellation_matches_reference` and
   `netting_residual_is_what_cancellation_yields`.
4. (focal) Which partition reports exist is a result rather than a given. The
   register names three operators and seven zones, and the epoch clears with
   five zones in scope. The two zones the suspension cascade emptied must have
   no report at all. Defeats `partition_membership_derived`.
5. (drift) Every experienced instinct about rounding and averaging is wrong
   here in one place or another. The clearance places every intermediate value
   on a settlement grid, but the assurance margin is the one division in the
   whole reference set that truncates and is never placed. The assurance
   median takes the lower of the two middle values of an even sample rather
   than averaging them, and the same convention is used again for the median
   absolute deviation. A solver who reaches for the ordinary mean of the two
   middle values moves the threshold and with it the holdback set, the pool,
   the apportionment and the digest. Defeats
   `assurance_margins_truncate_not_place` and
   `assurance_holdback_threshold_uses_mad`.
6. (trap) The coverage obligation only bites when a zone's cap is tight enough
   that curtailment would otherwise take a gate's last priced tap. In the
   shipped epoch curtailment withdraws two taps and never meets the
   obligation, so an implementation that ignores it clears the shipped epoch
   perfectly and then fails the corpus whose caps are tightened to a fortieth
   of their published value. Defeats `coverage_obligation_holds` and
   `generalises_across_suspension_and_cap_corpora`.
7. (trap) Both layers below the clearance have a threshold that is crossed
   only by a value standing strictly above it. A tap whose deviation sits
   exactly on the assurance threshold is retained, and a gate whose burden
   sits exactly on its allowance is not suspended. Neither case is visible on
   the happy path of the shipped epoch; the corpus with every allowance set to
   zero and the corpus with sigma set to zero are what surface them. Defeats
   `generalises_across_suspension_and_cap_corpora` and
   `generalises_across_netting_and_assurance_corpora`.

The reference implementation is Python 3.12 using the standard library only.
Grading runs in two channels: a deterministic channel of thirty five checks
over the delivered artifacts and over the delivered program run against
mutated register sets, and a judged channel of nineteen criteria over the
trajectory and the final message.

Out of bounds: carrying this epoch's figures in the delivered program as
constants, which `negative_hardcoded_epoch_answers` catches by running the
program against a corpus whose epoch boundary is narrower and seeing this
epoch's charge come back; letting the account depend on the order the register
rows arrive in, which `negative_output_depends_on_register_row_order` catches
by clearing the same registers twice with the rows reversed once; and writing
into the register directory the program was handed, which
`negative_program_rewrites_its_registers` catches by digesting that directory
before and after the run.

## Load-bearing work

The graded artifacts are the twenty eight paths under `/app/out` that a
correct clearance of the shipped epoch produces:

- `clear_epoch.py`, the reusable clearance program.
- `summary.json`, `reconciliation.json`, `tap_ledger.json`,
  `data_quality.json`, `identity_register.json`, `suspension_register.json`
  and `cap_relief.json`, the epoch level account.
- `operator_crossline.json`, `operator_northline.json`,
  `operator_southline.json`, `zone_alder.json`, `zone_cinder.json`,
  `zone_dovecote.json`, `zone_elmgate.json` and `zone_foundry.json`, the eight
  partition reports the shipped epoch leaves in scope. The instruction names
  ten candidates; `zone_bramble.json` and `zone_gantry.json` are the two the
  suspension cascade empties, and they must not exist. They are deliberately
  absent from the declared artifact list, because the harness errors a trial
  whose declared artifact is missing, and `task.toml` never reaches the agent
  so their absence from it gives nothing away.
- `netting_summary.json`, `netting_obligations.json`,
  `netting_residual.json`, `netting_positions.json`,
  `netting_schedule.json` and `netting_cycles.csv`, the netting layer.
- `assurance_summary.json`, `assurance_margins.json`,
  `assurance_holdbacks.json`, `assurance_order.json`,
  `assurance_apportionment.json` and `assurance_ladder.csv`, the assurance
  layer.

Per deliverable contract:

- The program takes a register directory and an output directory as two
  positional arguments, runs on Python 3.12 with the standard library only,
  finishes inside 300 seconds, and carries no figure that is true only of this
  epoch. It recovers the seven properties from the calibration block that
  travels with whatever registers it is given.
- `summary.json` carries the epoch counts, the charge, the distance totals,
  the suspended gates, the unvalidated zones, the stood down operators, the in
  scope operators and zones, the cap infeasible zones, and the seven recovered
  properties under `resolved_parameters`.
- `reconciliation.json` carries the eleven named conservation identities in
  the schema's order, each with its two sides and a residual of zero.
- `tap_ledger.json` carries one row per tap in the register, in canonical
  order, with the identity work, the governing table, the gross fare, the unit
  fare, the disposition, the withdrawal reason and a running charge that
  closes on the epoch charge.
- The two layers below carry their own twelve artifacts under the key names
  and CSV headers the artifact schema fixes.
- Every JSON artifact is serialised as two space indented, key sorted JSON
  with one trailing newline, which is the byte form the single shipped example
  report demonstrates and which no prose anywhere describes.

Out of bounds by design: the rulebooks, the invariant statement, the artifact
schema and the example report are written for the solver and are deliberately
absent from the register directory the program is handed, so a program that
reads them rather than the registers cannot clear any other epoch.

## Verification

`tests/test.sh` clears any stale score, locks the verifier log directory to
root, strips group and other access from `/tests`, and hands grading to
rewardkit over `/tests` with `/app` as the workspace. It writes no score
itself. rewardkit scores `test_output.py` and `judge.toml` separately and
`tests/reward.toml` combines them, each at half weight.

Channel A is `tests/test_output.py`: thirty five checks, thirty two positive
summing to 118 and three negative summing to -11. The channel's share runs
from -0.5 to 0.5 at `0.00423728813559322` per weight point.

Positive checks:

  - `program_delivered` (1)
  - `fixed_artifacts_present` (1)
  - `program_clears_an_arbitrary_register_set` (1)
  - `serialization_form` (1)
  - `summary_matches_reference` (5)
  - `recovered_properties_match_calibration` (5)
  - `unit_fares_match_reference` (5)
  - `dispositions_and_reasons_match_reference` (5)
  - `conservation_residuals_zero` (5)
  - `identity_resolution_matches_reference` (3)
  - `home_and_cross_operator_resolution` (3)
  - `suspension_fixpoint_matches_reference` (3)
  - `cap_relief_and_curtailment_match_reference` (3)
  - `coverage_obligation_holds` (3)
  - `partition_membership_derived` (3)
  - `partition_reports_match_reference` (3)
  - `ledger_order_and_running_total` (3)
  - `quality_register_matches_reference` (3)
  - `netting_obligations_match_reference` (5)
  - `netting_cycle_cancellation_matches_reference` (5)
  - `netting_residual_is_what_cancellation_yields` (5)
  - `netting_positions_and_schedule_match_reference` (3)
  - `netting_digest_matches_funding_order` (3)
  - `assurance_margins_truncate_not_place` (5)
  - `assurance_holdback_threshold_uses_mad` (5)
  - `assurance_apportionment_largest_remainder` (5)
  - `assurance_order_and_digest` (3)
  - `assurance_ladder_rendering` (3)
  - `generalises_across_identity_tariff_and_policy_corpora` (5)
  - `generalises_across_suspension_and_cap_corpora` (5)
  - `generalises_across_netting_and_assurance_corpora` (5)
  - `recovers_a_different_reading_from_shifted_calibration` (5)

Negative checks:

  - `negative_hardcoded_epoch_answers` (-5)
  - `negative_output_depends_on_register_row_order` (-3)
  - `negative_program_rewrites_its_registers` (-3)

Channel B is `tests/judge.toml`: nineteen criteria, sixteen positive summing
to 46 and three negative summing to -9, at `0.010869565217391304` per weight
point. The positive criteria judge the method and the report rather than the
artifacts: that the reference set was read before anything was written, that
candidate readings were tried against the published figures, that the
rulebooks were applied in dependency order, that the account was reproduced on
a second run and on a register directory with its rows in another order, that
the program reads its figures from the registers, that it is written in
ordinary style with its errors handled, that its imports are standard library
only, that the partition set was derived, that the conservation identities
were evaluated before the epoch was called closed, that the fault window
convention is taken from the recovered reading, that the cycles were cancelled
one at a time, and that the final message covers all three layers, works the
margin arithmetic through for two taps, states the share sum confirmation and
names each suspended gate with its reason. The three negative criteria catch
reading the grading surface, claiming a verification that was never run, and
running one failing command unchanged three turns in a row.

The rule that combines the two channels into one score belongs to the runner
harness. It must not be transcribed into this bundle, and no judged channel
score can be claimed for the oracle, because the oracle makes no model calls
and leaves no trajectory for a judge to read. Every oracle and empty run score
recorded anywhere for this bundle is a test channel score only.

## Root cause

**Specification without parameters.** A written rulebook can state every rule
and still leave a platform unusable, because a rule such as "the four
adjustments compose" is not a computation until the order is fixed. The seven
withheld properties are exactly the places where the rulebooks stop short of a
computation, and the calibration slice is the only evidence that closes them.
That is why the slice is built so each property moves at least one published
figure, and why a solver that matches eleven of the twelve figures has
recovered nothing.

**Mutual dependence needs a fixpoint.** Gate burden depends on withdrawals,
withdrawals depend on suspension, suspension depends on zone validation, zone
validation depends on which gates are suspended, and provisional zones couple
siblings across a whole operator. Each of those four state sets only grows, so
iterating to a fixpoint terminates and the fixpoint is unique. One pass is not
a fixpoint, and the pass count the account reports includes the confirming
pass that changed nothing.

**Order dependence is the point, not an accident.** Three separate orderings
carry real weight. The adjustment order changes the fare because every
adjustment's result is placed on the grid before the next sees it. The cap
release order changes which zone lends and therefore which taps survive
curtailment, because the operator's lending ceiling binds. The canonical cycle
order changes which cycles cancel and therefore the residual graph. None of
the three can be guessed from a plausible reading of the prose.

**Conventions do not inherit downward.** The netting and assurance rulebooks
sit on top of the clearance and borrow almost nothing from it. The assurance
margin truncates where the clearance places, the assurance median refuses to
average, the funding order is unrelated to canonical ledger order, and the
assurance digest order is unrelated to both. Each rulebook names its own
conventions, and taking a convention from the layer above is the single most
expensive mistake available.

**Red lines.** The account must be a function of what the registers say and of
nothing else: not the row order, not the file read order, not the wall clock,
and not what this particular epoch published. A program that carries this
epoch's answers, that moves with row order, or that edits the registers it was
handed has not cleared anything, and each of those three is caught by a
negative check of its own.

## Solution shape

1. Load every register, coercing each column to the type the schema gives it,
   and sort every table on its own key so nothing downstream sees file order.
2. Read the calibration block, enumerate the product of the seven candidate
   lists, and clear the embedded calibration slice under each reading,
   comparing the published figures cheapest first so a reading that already
   disagrees on pricing never pays for the netting and assurance passes.
   Exactly one reading survives all twelve figures.
3. Admit the taps: apply the epoch boundary convention, withdraw repeated tap
   identifiers after the first in canonical order, and withdraw taps at
   decommissioned gates.
4. Resolve every admitted tap's identity as at its own instant by walking the
   redirection in force, breaking a cycle on the smallest identity it
   contains, and letting a revocation outrank a retirement on any member of
   the chain. Then settle each identity's home operator from its earliest
   admitted tap and mark the cross operator taps.
5. Price each surviving tap: select the governing tariff table, pick the rate
   and the completion multiplier, form the gross fare and place it, compose
   the four adjustments in the recovered order with a grid placement after
   each, and let the gate floor bind once at the end.
6. Resolve the reversal records and their recovered reach, then drive the gate,
   zone, provisional and operator states to their fixpoint, withdrawing as the
   states move.
7. Apply the upheld exceptions to taps that are still priced, reviving none.
8. Settle the release order, lend surplus between sibling zones under the
   operator's float ceiling, then curtail each zone still over its effective
   cap while honouring the coverage obligation, recording any zone left cap
   infeasible.
9. Build the ledger in canonical order with its running charge, derive the in
   scope operators and zones, and emit only their reports.
10. Raise one obligation per priced cross operator tap, cancel cycles in
    canonical cycle order until the graph is acyclic, compute net positions,
    order the residual edges into the funding schedule against each payer's
    funding ceiling, and fold the digest over that order.
11. Take one margin per priced tap with positive distance by truncating
    division, take the median and the median absolute deviation by the lower
    middle convention, hold back what stands strictly above the threshold,
    pool the rest, apportion the retained distance by largest remainder, and
    fold the digest over the retained taps by ascending margin.
12. Evaluate the eleven conservation identities and write every artifact as
    two space indented, key sorted JSON with a trailing newline, plus the two
    CSV renderings.

## Ordered plan

1. Read all nine rulebooks, the invariant statement, the artifact schema, the
   calibration note and the example report before writing a line. This earns
   `r1_reads_the_reference_set_before_writing`.
2. Work out the order the rulebooks bear on a tap from the consumes and
   produces lines each one opens with, and note the three orderings the
   invariant statement fixes by hand because no dependency forces them. This
   earns `r3_orders_the_rulebooks_by_dependency`.
3. Build the clearance for one reading of the seven properties, parameterised
   rather than hard coded, so a reading can be swapped in cheaply. This earns
   `r6_reads_every_epoch_figure_from_the_registers` and
   `r11_takes_the_fault_window_from_the_recovered_reading`.
4. Clear the embedded calibration slice under every candidate reading and keep
   the one that reproduces all twelve published figures. This earns
   `r2_searches_the_calibration_space`.
5. Clear the shipped epoch, then drive the suspension states to a fixpoint and
   check the pass count includes the confirming pass.
6. Add the netting layer, cancelling cycles one at a time and recording each
   cancellation. This earns `r12_cancels_the_obligation_cycles_one_at_a_time`.
7. Add the assurance layer, taking every convention from its own rulebook.
8. Derive the in scope sets and emit only their reports. This earns
   `r9_derives_the_partition_set`.
9. Evaluate the eleven identities and confirm each residual is zero. This
   earns `r10_checks_the_conservation_identities`.
10. Clear the same registers a second time and compare, then clear a register
    directory with every row order reversed and compare again. These earn
    `r4_reruns_the_program_to_confirm_repeatability` and
    `r5_checks_row_order_independence`.
11. Review the delivered program for standard library imports only and for
    handled error paths. These earn `r8_uses_only_the_standard_library` and
    `r7_program_written_in_ordinary_style`.
12. Write the final message covering all three layers, with the margin
    arithmetic worked through for one retained and one held back tap, the
    share sum confirmation, and each suspended gate with its reason. These
    earn `r13_reports_all_three_layers`,
    `r14_shows_the_margin_arithmetic_for_two_taps`,
    `r15_states_the_share_sum_confirmation` and
    `r16_reports_the_suspension_reason_per_gate`.

## Pitfalls

- Settling the suspension states in one pass. The shipped epoch needs two,
  and the cascade through the provisional zone only appears on the second.
  Fails `suspension_fixpoint_matches_reference`.
- Offsetting mutual obligation pairs and calling the graph netted. The shipped
  epoch still carries a three node cycle after the pairs cancel. Fails
  `netting_cycle_cancellation_matches_reference` and
  `netting_residual_is_what_cancellation_yields`.
- Averaging the two middle values of an even sample. The assurance rulebook
  takes the lower of them, and the median absolute deviation uses the same
  convention, so the threshold moves twice. Fails
  `assurance_holdback_threshold_uses_mad`.
- Placing the assurance margin on the settlement grid because every other
  division in the reference set is placed. Fails
  `assurance_margins_truncate_not_place`.
- Writing a report for every operator and zone in the register. Two zones end
  out of scope and must have no report. Fails `partition_membership_derived`.
- Apportioning the epoch's priced distance rather than the retained distance.
  Fails `assurance_apportionment_largest_remainder` and leaves the
  `assurance_shares_sum_to_retained_distance` identity with a residual, which
  fails `conservation_residuals_zero`.
- Treating a value sitting exactly on a threshold as over it, for the gate
  allowance or for the assurance threshold. Fails
  `generalises_across_suspension_and_cap_corpora`.
- Recovering the seven properties against a subset of the published figures.
  Several properties move only one figure, so a partial comparison leaves more
  than one reading standing. Fails
  `recovers_a_different_reading_from_shifted_calibration`.
- Resolving identity as of the end of the epoch rather than as at each tap.
  Fails `identity_resolution_matches_reference`.
- Taking the home operator from the earliest priced tap rather than the
  earliest admitted one. Fails `home_and_cross_operator_resolution`.
- Curtailing a gate's last priced tap. Fails `coverage_obligation_holds`.
- Reading the rulebooks at run time from the register directory. They are not
  there, so every corpus run crashes. Fails every generalisation check.

## Provenance

```yaml
uuid: 5b46e176-ff53-5506-9ae6-45b371a9a9f0
instance_id: 5b46e176-ff53-5506-9ae6-45b371a9a9f0
task_name: terminal-bench/5b46e176-ff53-5506-9ae6-45b371a9a9f0
fix_patch_sha256: 04c2049d3a1b42cc7c53ca0a105a436d0d677bc10e5dd82d3a83cad8566b037f
solve_py_sha256: 2e1d90058b4330783a7a613ba2a491b628d820d7271cb6b51f536a21994081da
language: Python 3.12, standard library only
authored_by: null  # attribution lives in task.toml authors, not in a client delivery file
status: execution gate run, test channel measured
measured_oracle_test_channel: 1.000  # harbor 0.24.0, five runs, tests-only copy
measured_empty_test_channel: 0.000  # harbor 0.24.0, nop agent, tests-only copy
measured_stub_test_channel: 0.000  # harbor 0.24.0, stub solution, tests-only copy
withheld_property_count: 7
calibration_search_space: 122880
calibration_readings_admitted: 1
corpora_embedded: 49
graded_artifacts: 28
partition_candidates_named: 10
partition_reports_in_scope: 8
```
