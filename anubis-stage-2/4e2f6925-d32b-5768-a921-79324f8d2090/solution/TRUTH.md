# TRUTH.md - 4e2f6925-d32b-5768-a921-79324f8d2090

The whole derivation, the grading contract and the author side evidence. This
file is kept out of the agent image.

## Defect

There is no broken program here. The defect the agent has to repair is a
missing recomputation: the publication interval was withdrawn and never
republished, and every figure has to be derived from the working papers. What
follows are the decisions the derivation turns on. Each is stated normatively
in its stage specification and restated in the numbered footgun list of
`known_traps_and_footguns.md`, and each is reverted in isolation by the author
side mutation matrix in `Verification`.

Focal decisions, the ones the spine hangs off.

1. `R_LOCK_STATE` (focal) Only an attempt in lock state LOCK_HELD is eligible
   to be the canonical reading of its cluster. The greatest attempt number of
   a cluster is usually held by a row that lost lock.
2. `R_CAL_APPLICABLE` (focal) The applicable delay report is the one with the
   greatest effective epoch on or before the reading. The report that reached
   the desk last takes effect after the interval closes.
3. `R_CAL_NANOSECOND` (focal) The ledger publishes delays in nanoseconds and
   every reading is in picoseconds.
4. `R_TREE_UNCERTAINTY` (focal) The spanning tree admits on the uncertainty
   the register publishes, not on the order the candidates were found in.
4a. `R_TREE_PATH_COST` (focal) The admission works on the uncertainty a node
   accumulates back to the root of its component, the path cost of the reached
   end plus the candidate's own uncertainty, and not on the candidate in front
   of it. The minimum spanning tree of the component is a different tree, and
   the corpus separates them: the shortest path reading admits `lk_cb02` and
   the minimum spanning tree reading admits `lk_be05`. The quantity the
   admission minimises is the one stage T12 publishes as the path terms of a
   node's budget, so the two stages agree about what a node carries.
5. `R_TWO_POINT_SLOPE` (focal) The prediction frequency is the slope through
   the first and last valid deviation of the history window, not a least
   squares fit.
6. `R_CAP_REDISTRIBUTE` (focal) Capping is mass preserving; the excess is
   handed to the holders below the cap in proportion to what they hold.
6a. `R_DAMPED_STEP` (focal) The capping pass moves the vector a fraction of the
   way toward the capped target rather than taking the full step, and it damps
   every oscillator rather than only the offenders. The map has a fixed point
   with a closed form; the published vector is the k-th damped iterate, which
   no closed form gives.
6b. `R_PASS_QUANTISATION` (focal) Every pass places the vector back on the
   published weight grid and the next pass starts from the placed values, so
   the passes are not independent. This is the second of the two carried
   roundings in the chain.
6c. `R_PLACEMENT_RESIDUE` (focal) Placing a pass on the grid moves the total of
   the vector, because half to even sends some weights up and some down and the
   two do not cancel. The pass hands the whole of that difference to one
   receiving holder, which 6d names, so the total after a pass equals the total
   before it exactly. The natural implementation places each weight and lets
   the total drift, and the drift is carried into every later pass.
6d. `R_RESIDUE_ROTATION` (focal) Which holder closes the placement residue is
   not fixed. It is the receiving holder that has carried the residue the
   fewest times so far in the interval, a tie going to the greatest weight
   after placement and then to the smallest identifier, counted across every
   pass of all three phases. The count is solver state: a pass cannot be worked
   out from the vector it starts from alone, so the published vector is not
   recoverable by reading the pass rule correctly one pass at a time. The
   natural implementation closes onto the greatest receiver every pass.
7. `R_CAP_ORDER` (focal) The oscillator cap runs first, then the node cap,
   then exactly one further oscillator sweep. The order changes the answer.
8. `R_ROUND_AT_WRITE` (focal) The ensemble quotient is formed exactly and
   rounded once when written.
9. `R_EPOCH_DENOMINATOR` (focal) The ensemble denominator is the weight of the
   oscillators contributing at that epoch, not the ensemble total.
10. `R_FROZEN_REGISTER` (focal) Node metadata comes from the register revision
    the interval header freezes.

Drift decisions, each one a stage rule a careful reader still gets wrong.

11. `R_WITHDRAWN_SESSIONS` (drift) The journal withdraws acquisition sessions
    before clustering, and a cluster that loses its only locked attempt then
    falls to DR_NO_LOCKED_ATTEMPT.
12. `R_INTERVAL_BOUNDS` (drift) A row attributable to no epoch is set aside,
    never moved to the nearest one.
13. `R_WINDOW_HALF_OPEN` (drift) The attribution window is closed below and
    open above.
14. `R_NEAREST_WINS` (drift) A tie on attempt number goes to the acquisition
    nearest the epoch instant, and only then to the earlier acquisition.
15. `R_CAL_REVISION_TIE` (drift) Two reports sharing an effective epoch resolve
    to the smaller revision.
16. `R_SENSE_NORMALISE` (drift) Two of the four techniques record the opposite
    measurement sense.
17. `R_TREE_TECHNIQUE_TIE` (drift) A tie on published uncertainty goes to the
    smaller technique rank before it goes to the link identifier.
18. `R_UNANCHORED_ROOT` (drift) An unanchored component roots at its
    lexicographically smallest node.
19. `R_UNANCHORED_EXCLUDE` (drift) Oscillators on unanchored nodes leave the
    ensemble and keep their published series.
20. `R_NO_INTERPOLATION` (drift) Dead time stays absent.
21. `R_HISTORY_MINIMUM` (drift) The memo minimum is compared strictly, so
    exactly the minimum is enough.
22. `R_PUBLISHED_DISPERSION` (drift) The weight is formed from the published
    whole picosecond dispersion. This is the first of the two carried roundings
    of the chain, the other being the grid placement of every capping pass.
23. `R_ZERO_DISPERSION_CEILING` (drift) A zero dispersion oscillator takes the
    ceiling weight of its class from the workbook.
24. `R_FINAL_OSC_SWEEP` (drift) Exactly one further oscillator sweep, whatever
    the budget says.
25. `R_SWEEP_BUDGET` (drift) The first pass stops at the published budget and
    records that it did.
26. `R_STEER_NEXT_EPOCH` (drift) The steering correction starts at the epoch
    after the decision epoch.
27. `R_STEER_TRUNCATE` (drift) The step is truncated toward zero onto the
    grid, so a step below one grid unit becomes zero.
28. `R_UNCERTAINTY_LINEAR` (drift) The budget publishes a variance in square
    picoseconds and a conservative linear sum in picoseconds.
29. `R_ROW_ORDER` (drift) Three artifacts carry a stated row order that is not
    the identifier order.
30. `R_DIGEST_ORDER` (drift) The core digest runs in chain order, not in
    alphabetical order.

Traps, the material in the corpus that makes a wrong reading look right.

31. `node_register_current.csv` (trap) The latest register revision, disagreeing
    with the frozen one on two reference oscillators and on every declared
    uncertainty. Disavowed in `data_lineage.md`.
32. `legacy_weight_table.csv` (trap) The fixed class weight scheme the network
    retired at REG-R09. Disavowed in `data_lineage.md` and in
    `governance_revision_notes.md`.
33. `topology_drafts.xml` (trap) An uncommissioned rerouting with reversed
    endpoints. Disavowed in `data_lineage.md`.
34. The superseded workbook sheet (trap) Doubled class ceilings and a
    different node cap. Both sheets carry a revision label that says nothing
    about which one is in force, both keys are minted in one shape, and the
    two sit in the workbook in revision order, so the live sheet is found by
    matching its key cell against `network_config.json` and by nothing else.
    The live sheet is the second of the two on three of the four graded
    intervals and the first of them on CHALLENGE.
35. `lk_ah10` (trap) Every calibration report of this link takes effect after
    the interval closes, so it has no applicable report and its selection rows
    carry CAL_ABSENT.
36. `lk_ff18` and `lk_absent_99` (trap) A self loop and an unregistered link,
    both carrying readings that never reach the ledger.
37. Two acquisition rows that satisfy two set aside predicates at once (trap).
    One falls in no attribution window and is also named in the withdrawal
    journal, and one names an unregistered link and is also withdrawn. The
    predicates are ordered and the first match is the reason, so these two
    rows are what makes that order decide anything.
38. `lk_jk17` and `lk_jk18` (trap) Two links joining the same pair of nodes at
    equal published uncertainty AND equal technique rank, so the third key of
    the admission chain, the link identifier, decides between them.
39. `nd_kelvin` (trap) Its tree edge carries no locked attempt at any epoch, so
    the node is in an unanchored component and carries no published offset at
    the same time, and the order the T12 statuses are tested in decides which
    withheld status it takes.

## Load-bearing work

The corpus is sixty flat working papers. Four control values live only inside
`network_calibration_memo.pdf`: `OSC_WEIGHT_CAP_NUMERATOR`,
`OSC_WEIGHT_CAP_DENOMINATOR`, `CAP_SWEEP_BUDGET` and
`HISTORY_MINIMUM_EPOCHS`. Three more live only on the live sheet of
`timing_network_workbook.xlsx`: the five class ceiling weights, the node weight
cap numerator and denominator, and the two hundred and ten row uncertainty
component table. Without the memo, stages T07 and T09 cannot run. Without the
live sheet there is no ceiling weight for the zero dispersion oscillator, no
node cap and no uncertainty budget.

The rest of the load bearing material is the acquisition log of one thousand
and eighty one attempts, the withdrawal journal of eleven sessions, the local
monitor log of five hundred and forty rows, the archive of six hundred and
seventy two prior deviations, one hundred and twenty two calibration reports
across the ledger and its supplement, and the seven policy papers.

Every control value moves off its shipped value in at least one minted
interval that consults it. The memo publishes 1/12, a budget of 4 and a
history minimum of 8 on the shipped interval; EVAL publishes 2/20, 5 and 5,
CHALLENGE 3/24, 6 and 8, and PROBE 2/20, 5 and 6. The oscillator cap
numerator never repeats the shipped 1, the sweep budget never repeats the
shipped 4, and EVAL and CHALLENGE both run the first pass to their budget.
The node weight cap share and the five class ceilings are drawn per interval
as well, and EVAL carries a flat history window on `osc_ar03`, `osc_bo02`,
`osc_du01` and `osc_fa02`, so an oscillator of every one of the five classes
publishes zero dispersion there and takes its class ceiling. A program that
holds any one of these values instead of reading the memo and the live sheet
reproduces the shipped bytes and fails at least one minted interval.

The third capping pass finds an offender when the first pass stops on its
budget with an oscillator still above the cap and the node pass does not bring
it back under. SAMPLE and EVAL reach that state and publish a `PH_FINAL_SWEEP`
trace record. CHALLENGE does not: its node pass sets `nd_calder` on the node
cap and leaves no oscillator above the oscillator cap. PROBE does not either,
because its oscillator cap is unsatisfiable. The node pass moves weight on
SAMPLE and CHALLENGE and publishes a `PH_NODE_CAP` record there; on EVAL and
PROBE no node sits above the node cap and the pass writes no record.

`corpus_sentinel_note.txt` states the branches the shipped acquisition profile
leaves quiet: a void epoch, an unsatisfiable oscillator cap, a decision epoch
with no primary realisation, and a link whose applicable report comes from the
supplement at a link whose ledger reports all take effect after the interval
closes. The sparse interval the verifier mints reaches the first three and the
program tier grades it; the fourth is stated for completeness and this
interval set does not reach it.

## Verification

Channel A is `tests/test_output.py`, eighteen positive functions and sixteen
negative detectors, a positive weight total of 74 and a negative total of
minus 62.

Two functions carry weight 1 and are the existence floor, so a well formed but
wrong delivery banks 2.70 percent. Four carry weight 3 and grade the four
artifact families of the shipped interval. Twelve carry weight 5 and grade the
four families of each of the three minted intervals, the seven artifact core
included. Sixty of the seventy four positive points ride on the delivered
program.

Every family is graded on its own documents and nothing else, so a stage read
differently costs the families whose documents it moves and no others. The
manifest carries a publication digest over the other twenty six artifacts, so
any artifact that moves also moves the manifest and costs the core family of
that interval as well as its own.

Stage T09 states the total the two caps are taken from twice: its opening
paragraph forms W from the raw weights, and its grid paragraph, with trap 47,
takes the total of the weights placed on the grid. The verifier reconstructs
every interval under both readings and a family passes when its documents
match either one. The switch that selects the reading is not a rule and does
not count toward `rule_count`. The oracle takes the placed total.

Eight of the sixteen detectors rebuild the whole pipeline under one named wrong
reading and fire only when the delivered bytes equal that reconstruction:
`test_negative_weight_unlocked_attempt_selected`,
`test_negative_weight_latest_issued_calibration`,
`test_negative_weight_least_squares_prediction`,
`test_negative_weight_clamped_weight_vector`,
`test_negative_weight_fixed_residue_carrier`,
`test_negative_weight_rounded_before_the_average`,
`test_negative_weight_current_node_register` and
`test_negative_weight_steering_from_the_decision_epoch`. Each short circuits on
an answer that matches either graded reading of stage T09 and each raises
rather than returning when an artifact is absent, which is what keeps the
oracle at 1.000 and the empty container at 0.000 on the test channel.

The other eight cover conduct rather than a reading:
`test_negative_weight_hardcoded_sample_answers`,
`test_negative_weight_manifest_digest_mismatch`,
`test_negative_weight_program_ignores_its_input`,
`test_negative_weight_nondeterministic_output`,
`test_negative_weight_filename_dependent_behaviour`,
`test_negative_weight_program_dirties_its_directories`,
`test_negative_weight_reads_training_corpus_at_runtime` and
`test_negative_weight_rebinds_verifier_dependencies`.

Each of the eight is carved to one triggering action, and four pairs that could
otherwise overlap short circuit on each other: determinism against filename
dependence, the constant core against the shipped corpus at runtime, the
dirtied directory against the shadowing module, and the copied answer against a
program that runs. A program that FAILS on a minted interval is a pipeline with
a bug rather than a copy, so
`test_negative_weight_hardcoded_sample_answers` raises on a non zero exit and
fires only where the program is absent or exits cleanly having written nothing:
a pipeline that fails on a minted interval forfeits the twenty points of that
interval and is charged nothing on top of it.

Channel B is `tests/judge.toml`, sixteen criteria totalling 39 positive
points and minus 21 negative, ten of them instruction following and leading
the file, five of them negative. No criterion grades an artifact value; every
one grades the trajectory or the final message. Nine of the ten leading
criteria carry the nine items the instruction asks for in the final message,
and the tenth carries the rule that the signed memo is read for the control
values it alone publishes. One positive criterion, at weight 3, judges how
the delivered program is written. The five negatives cover the retired weight
table, a reported figure that disagrees with its artifact, an unearned byte
exact claim, dead time filled from another epoch and a control value reported
from the wrong workbook sheet.

The stage rules themselves are graded by the test channel alone, because each
of them settles bytes the tests compare. No criterion is a complement of
another, and no judged negative shares a triggering action with a test
negative.

### Per rule liveness

Every one of the thirty five stated decisions was reverted alone against the
shipped corpus and against all three minted intervals, and every one moved at
least one graded document on the shipped interval. All thirty five rows are
below. Counts of moved artifacts on the shipped interval, out of twenty seven:

    R_WITHDRAWN_SESSIONS 20   R_LOCK_STATE 21          R_INTERVAL_BOUNDS 16
    R_CAL_APPLICABLE 17       R_CAL_REVISION_TIE 17    R_CAL_NANOSECOND 17
    R_SENSE_NORMALISE 16      R_TREE_UNCERTAINTY 19    R_TREE_TECHNIQUE_TIE 18
    R_TREE_PATH_COST 19       R_UNANCHORED_ROOT 11     R_UNANCHORED_EXCLUDE 17
    R_WINDOW_HALF_OPEN 16     R_NEAREST_WINS 2         R_NO_INTERPOLATION 16
    R_FROZEN_REGISTER 16      R_TWO_POINT_SLOPE 15     R_HISTORY_MINIMUM 17
    R_PUBLISHED_DISPERSION 14 R_ZERO_DISPERSION_CEILING 16
    R_CAP_REDISTRIBUTE 13     R_DAMPED_STEP 13         R_PASS_QUANTISATION 11
    R_PLACEMENT_RESIDUE 11    R_CAP_ORDER 14           R_FINAL_OSC_SWEEP 13
    R_RESIDUE_ROTATION 10
    R_SWEEP_BUDGET 13         R_EPOCH_DENOMINATOR 11   R_ROUND_AT_WRITE 11
    R_STEER_NEXT_EPOCH 9      R_STEER_TRUNCATE 11      R_UNCERTAINTY_LINEAR 8
    R_ROW_ORDER 5             R_DIGEST_ORDER 1

Eleven of the thirty five are inert on the sparse probe interval, whose
oscillator cap is unsatisfiable so its capping runs no pass at all and whose
decision epoch carries no realisation to steer onto, and `R_STEER_NEXT_EPOCH`
is inert on CHALLENGE and `R_STEER_TRUNCATE` on EVAL, where the steering
outcome each of them turns on does not arise. Every one of the thirteen is
live on the shipped interval, and each is live on at least one minted interval
as well, so every decision is graded on the program tier.

The ordering and tie break chains were traced pair by adjacent pair against the
fixtures, not against the rule names. The five set aside predicates of stage
T01 carry a row that falls in no attribution window and is also withdrawn, and
a row that names an unregistered link and is also withdrawn, so the first two
adjacent pairs decide. The four exclusions of stage T07 carry the
decommissioned oscillator with no archive row at all, which decides the first
pair, and the oscillator with no archive row whose window is also short, which
decides the second; the sparse interval carries five oscillators that are both
short of history and on an unanchored node, which decides the third. The
admission chain of stage T04 carries `lk_ce14` against `lk_ce15` at equal cost
and different technique rank, and `lk_jk17` against `lk_jk18` at equal cost and
equal rank. The two withheld dissemination statuses of stage T12 are decided by
`nd_kelvin`, which is unanchored and carries no published offset at once.

The one pair that decides nothing is the unregistered link against the self
loop, and no corpus can separate them: a self loop is a link the register
carries, so a row cannot satisfy both predicates at the same time.

`R_DIGEST_ORDER` moves one artifact, the manifest, and the manifest is in the
core family, so that one artifact costs the core family of every interval.

### Graded surface coverage

Every member of every closed vocabulary the tests compare appears in a graded
corpus, asserted on all four seeds: the four lock states, the four archive
quality flags, the two monitor flags, the four link techniques, the two
measurement senses, the five oscillator classes, the two oscillator statuses,
the three calibration statuses, the five register revisions, the five drop
reasons, the four exclusion reasons, the two component roles, the three sweep
outcomes, the three steering outcomes, the two epoch states, the three series
flags, the two weight sources, the three dissemination statuses, the two offset
flags, the three dead time scopes and the three sweep phases.

### Per rule mutation matrix

Each row is a solver that implements the whole specification correctly except
for the one decision named, in the delivered bytes and in the delivered program
alike, measured through the shipped weight table.

    R_LOCK_STATE                   +0.027027   detector -5
    R_CAL_APPLICABLE               +0.027027   detector -5
    R_ROW_ORDER                    +0.027027
    R_FROZEN_REGISTER              +0.054054   detector -3
    R_CAL_NANOSECOND               +0.094595
    R_CAL_REVISION_TIE             +0.094595
    R_TREE_PATH_COST               +0.094595
    R_TREE_TECHNIQUE_TIE           +0.094595
    R_TREE_UNCERTAINTY             +0.094595
    R_TWO_POINT_SLOPE              +0.202703   detector -5
    R_INTERVAL_BOUNDS              +0.270270
    R_NO_INTERPOLATION             +0.270270
    R_PUBLISHED_DISPERSION         +0.270270
    R_ROUND_AT_WRITE               +0.270270   detector -5
    R_UNANCHORED_ROOT              +0.270270
    R_WINDOW_HALF_OPEN             +0.270270
    R_WITHDRAWN_SESSIONS           +0.270270
    R_HISTORY_MINIMUM              +0.297297
    R_UNANCHORED_EXCLUDE           +0.297297
    R_ZERO_DISPERSION_CEILING      +0.297297
    R_EPOCH_DENOMINATOR            +0.337838
    R_SENSE_NORMALISE              +0.337838
    R_CAP_ORDER                    +0.405405
    R_CAP_REDISTRIBUTE             +0.405405   detector -5
    R_RESIDUE_ROTATION             +0.405405   detector -5
    R_DAMPED_STEP                  +0.472973
    R_PASS_QUANTISATION            +0.472973
    R_PLACEMENT_RESIDUE            +0.472973
    R_SWEEP_BUDGET                 +0.472973
    R_UNCERTAINTY_LINEAR           +0.513514
    R_FINAL_OSC_SWEEP              +0.540541
    R_STEER_TRUNCATE               +0.675676
    R_DIGEST_ORDER                 +0.702703   detector -3
    R_STEER_NEXT_EPOCH             +0.743243   detector -3
    R_NEAREST_WINS                 +0.756757

The thirty five rows are the whole set. Every decision costs points and none
reaches full marks; the lightest single reversal, `R_NEAREST_WINS`, keeps
0.756757. Nine rows carry their own detector: eight because the delivered
bytes equal the reconstruction that detector rebuilds, and `R_DIGEST_ORDER`
because a core digest taken in alphabetical order disagrees with the bytes
published beside it and also moves the `core_order` the manifest carries,
which costs it the second existence point as well.

A decision whose documents reach every family of every interval sits on the
existence floor: `R_ROW_ORDER` keeps nothing else, and `R_LOCK_STATE` and
`R_CAL_APPLICABLE` keep only the probe weight family, which their detectors
take back. A compound solver taking four of the fluent readings at once, the
unconverted nanosecond delay, the least squares prediction, the naive clamp and
the rounded residual, scores -0.040541.

### Absence proof

Every declared artifact was removed one at a time from a correct delivery and
each removal cost points. Removing one document costs 5.4 percent, the shipped
family it belongs to and the existence point; removing the manifest, the link
graph or the prediction book costs 6.8 percent, because the shape check reads
them as well; and removing the program costs 86.5 percent. No artifact is
inert.

### Isolation

The verifier holds no reference to the agent corpus and graded 1.000 on the
test channel in a process with no `/app/data`. The delivered program pointed
at an empty directory exits non zero and names the paper it could not find,
writing nothing.

The delivered program is hostile input and it is not run as root.
`test_output.py` launches every run of it through `setpriv --reuid=nobody
--regid=nogroup --clear-groups`, and `tests/test.sh` takes the read and traverse bits off
`/tests` for every user but root. Without that pair a program of fifteen lines
that loads `/tests/test_output.py` and calls `run_pipeline` reproduces every
graded byte on every interval and scores 1.000 with none of the work done.
Verified in the built verifier image: root
still reads the module, `setpriv` reports uid 65534, and the same load as
nobody raises `PermissionError [Errno 13] Permission denied:
'/tests/test_output.py'` while `/tests` is not even listable.

### Honest solver, oracle and nop

`solution/solve.py` implements the specification completely and scores 1.000
on the test channel with no negative detector firing. An empty container
scores 0.000 on the test channel.

It is an independent implementation rather than the verifier's chain under
another name: a `Papers` loader, an `Interval` carrying thirteen
`stage_tNN_*` methods and a `Publication` writer, sharing no stage function, no
loader and no writer with `tests/test_output.py` and 12 percent of its
substantive lines, all of them structural. Written from the stage
specifications, it reproduces every reference byte on all four graded
intervals, which is the agreement an oracle run is supposed to be evidence of.

Measured twice on the bundle as it ships, on the test channel only. Through
the local grade loop on the shipped weight table, oracle raw +74 of 74,
reward 1.000000, and nop raw +0, reward 0.000000 with no test passing.

End to end against docker on the shipped bytes, test channel only, two
oracle runs, one nop run and one oracle run that leaves every file it writes
at owner only modes, every trial carrying `exception_info: null` and every
invocation exiting 0:

    oracle      step10run__wApXbkH  1.0
    oracle      step10run__n2ZgQzK  1.0
    nop         step10run__RFoVci2  0.0
    owner only  ownerrun__ymLgEVS   1.0

The two oracle runs and the nop run graded one copy of the bundle, built once
before the first of them. No negative detector fired on any oracle run. The
verifier takes about twenty five seconds because it runs the delivered program
eight times across the three minted intervals.

A stub built from `task.toml` alone, creating each declared path empty and
doing nothing else, scores -0.0676 in trial `stubrun__bNM978i`: the existence
check pays +1 and the manifest digest detector and the dirtied output
directory detector take -3 each. Producing the twenty eight named files with
nothing behind them costs more than it earns.

## Root cause

The withdrawn publication left no figures behind, so nothing can be repaired in
place. The interval has to be rebuilt from the papers, and the papers are
written as a chain of thirteen stages in which each stage freezes a value the
next one consumes. The reason a competent solver still gets it wrong is that
thirty five of the decisions in that chain have a fluent default that the
papers contradict, and a decision read the other way moves every document
downstream of the stage that holds it. Each family is graded whole, and the
publication digest in the manifest binds every document to the core family,
so one early decision read the other way costs most of the delivery rather
than one file.

## Solution shape

Read the sixty papers, of which two are binary and load bearing. Run the
thirteen stages in exact rational arithmetic, carrying int and Fraction and
nothing else, and round only where the stage specification places the rounding.
Emit twenty seven documents in nine formats and the reusable program that
regenerates them from any interval of the same network.

`solution/solve.py` is that program. It is an independent implementation of the
thirteen stage specifications, the output schema reference and the
serialisation contract, written against the shipped papers rather than against
the verifier: a `Papers` loader, an `Interval` carrying thirteen
`stage_tNN_*` methods and a `Publication` writer, on the standard library
alone. It shares no stage function, no loader and no writer with
`tests/test_output.py`, which is what makes the oracle run evidence: two
implementations that were written apart agree only when both are right.

## Ordered plan

1. Read `readme_first.txt`, `network_contract_overview.md`, `data_lineage.md`
   and `known_traps_and_footguns.md`.
2. Read the live workbook sheet by matching its key cell, and the memo.
3. T01: attribute, apply the five ordered predicates, pick the canonical
   reading of every cluster.
4. T02: merge the ledger and the supplement, select the applicable report,
   convert nanoseconds to picoseconds, apply.
5. T03: normalise the measurement sense.
6. T04: build the graph from the register, split components, root them, grow
   each spanning tree.
7. T05: sum the tree paths into node offsets and record dead time.
8. T06: build the deviation series from the node offsets and the local monitor.
9. T07: predict every oscillator through the endpoints of its history window
   and apply the four exclusions in order.
10. T08: take the mean absolute residual, publish it as a whole picosecond and
    form the raw weight from what was published.
11. T09: oscillator cap, node cap, one further oscillator sweep.
12. T10: form the free scale exactly, per epoch, over the contributing weight.
13. T11: steer, truncating the step toward zero and starting at the epoch after
    the decision.
14. T12: publish the offsets and the two uncertainty statistics.
15. T13: reconcile the excluded links, write the reports, take the two digests
    and write the manifest last.

## The reproduction fidelity core

Stages T01 to T08 and T10 to T13 are discrete decisions: which key, which
order, which sheet, which comparator. Reading rules is measured, on this box
and elsewhere, not to be a difficulty lever against a frontier solver.

Stage T09 is a different kind of demand. The published weight vector is the
fourth damped iterate of a cap and redistribute map, placed back on a six
decimal grid at the end of every pass. Reproducing it needs the damping applied
to the whole vector rather than the offenders, the grid placement applied after
the damped step rather than before it, the residue of that placement closed
onto the receiving holder that has carried it the fewest times rather than left
to drift, the offender test strict rather than inclusive, and the pass count
taken from the memo rather than run to convergence. Off by one on any of those
gives different bytes, and the weight book publishes every weight to twelve
decimal places, so the difference is visible immediately and moves the
publication digest with it.

Five properties of the stage were measured on all four seeds:

  * the budget truncates before convergence. The oscillator cap records
    SW_BUDGET_EXHAUSTED on every non sparse seed, and the offender count rises
    across the passes (1, 3, 4, 4 on the shipped interval, 3, 3, 4, 4, 4 on
    EVAL and 1, 1, 1, 2, 2, 3 on CHALLENGE) because redistribution pushes
    holders over the cap.
  * the damped iterate differs from the fixed point. Iterating to convergence
    moves 13 of the 27 artifacts.
  * the per pass grid placement matters. Carrying the exact rational between
    passes moves 11 of the 27 artifacts.
  * the residue of that placement matters on its own. Placing each weight and
    letting the total drift, which is what an implementation that does not read
    the paragraph writes, moves 11 of the 27 artifacts and scores +0.472973.
  * which holder closes the residue matters, and it is the one piece of the
    stage that is solver state rather than a rule. Closing onto the greatest
    receiver every pass moves 10 of the 27 artifacts on the shipped interval,
    11 on each of the two strained minted intervals, and scores +0.405405: the
    delivery keeps only the families the weight vector does not reach and its
    own detector fires. It is inert
    on the sparse probe interval, whose oscillator cap is unsatisfiable and
    whose sweep runs no pass at all.

The third pass finds an offender on the shipped interval and on EVAL, where it
records SW_BUDGET_EXHAUSTED and publishes a PH_FINAL_SWEEP trace record, and
finds none on CHALLENGE, where it records SW_SETTLED and writes no record. The
node cap share each interval draws is what decides between the two.

No restart clause is shipped. Cap and redistribute is a monotone contraction,
so a clause that fires after two non improving residuals is unreachable and
would be a dead rule.

## Pitfalls

These are the properties of the corpus that keep the stated rules gradeable.
Each one is a condition the interval has to carry, and each is checked on all
four graded intervals.

The link bias per edge is what makes the spanning tree rule live at all.
Without it the graph closes, every tree gives the same node offsets and
`R_TREE_UNCERTAINTY` grades nothing.

The node cap share has to be drawn from a set that leaves the third capping
pass an offender to act on, otherwise `PH_FINAL_SWEEP` is a published
vocabulary member no graded interval reaches: the pass would emit no trace
record and a solver that never implemented the record would lose nothing. The
share the four intervals draw reaches the state on SAMPLE and EVAL.

The tie `R_NEAREST_WINS` turns on has to put the acquisition nearest the epoch
instant and the earliest acquisition on different rows. A tie that puts both on
one row leaves the rule inert, because either reading picks the same attempt.

`CAL_PROVISIONAL` reaches a published row because one report per third link is
registered provisional at an effective epoch of its own.
`governance_revision_notes.md` says that the review status of a report takes no
part in selecting it, so a solver that filters on status is reading a field
that orders nothing.

The decommissioned oscillator carries no archive row. That is what makes the
first pair of the stage T07 exclusion chain decide anything: without it no
oscillator is both decommissioned and unarchived, and a solver testing
EX_NO_ARCHIVE before EX_DECOMMISSIONED publishes the same bytes.

Both workbook sheets carry a revision label that says nothing about which is in
force and a key minted in one shape, and the two sit in the workbook in
revision order. Without that the live sheet is always the second sheet and
always the one whose name says LIVE, and the rule that it is found by its key
cell grades nothing.

A leaf stage decision costs more than its own document because the
publication digest in the manifest runs over every document but the manifest,
so a leaf document read the other way moves the core family of every interval
it reaches as well as its own family. No family is gated on another, so a
decision costs the families whose documents it moves and no others. That is a
property a domain expert would expect of a publication, not a reweighting.

Every observable the tests grade byte exact has to be pinned by a shipped
paper. `timescale_report.md` and `ensemble_summary.md` carry a literal layout in
the schema reference rather than a cross reference to the serialisation
contract, the `sweep` counter inside `weight_sweep_trace.jsonl` is stated to
restart at 1 in each phase, and `valid_count` is stated to be published for
every oscillator whether included or excluded. `sample_worked_records.jsonl`
and `unit_test_vectors.json` carry worked arithmetic on invented values that
belong to no link and no epoch of this interval, so neither leaks a graded
value.

The zero dispersion oscillator needs a drift the grid represents exactly. One
grid step at one part in ten to the eighteenth is 864 ten thousandths of a
picosecond, so the drift has to be a multiple of 625 for the archived
deviations to sit on a straight line and the residuals to be exactly zero.

## Provenance

```yaml
uuid: 4e2f6925-d32b-5768-a921-79324f8d2090
instance_id: 4e2f6925-d32b-5768-a921-79324f8d2090
task_name: terminal-bench/4e2f6925-d32b-5768-a921-79324f8d2090
fix_patch_sha256: 483e1f18b3584f18b7593f9e6e6b6d62c37bbef3b7a5457bbcdf5dcaef5c7b15
solve_py_sha256: 0afcb3c1b36857442b66565b8f5e5e0d32dc2d6ac697e81c6937fdba41e1d08a
language: python
```
