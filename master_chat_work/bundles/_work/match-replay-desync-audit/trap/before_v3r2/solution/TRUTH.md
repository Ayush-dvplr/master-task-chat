# TRUTH.md - match-replay-desync-audit

## Defect

A turn based strategy title shipped a build whose replay serializer applied a
menu of space saving wire transforms to every capture it wrote. The header of
each capture carries a flag word naming which transforms are live, and the
studio's format note describes each transform, but nine of the numeric
parameters those transforms read were compiled into the shipping build and
appear in no file that went out with the captures. Two further parameters that
the settlement engine reads are withheld in the same way. The captures
therefore cannot be replayed until each of the eleven quantities is recovered
from the calibration slice that ships beside them, and the settlement they feed
cannot be reproduced until the engine's own cancellation rule is read as
written rather than as a reader expects.

- The eleven withheld quantities are recoverable only by trying each published
  candidate against the control figure that separates it, in the order the
  calibration slice lists them. **(focal)**
- Every flagged capture applies all twelve transforms at once, so a run that
  inverts eleven of them decodes nothing. **(trap)**
- The two captures whose flag word is zero decode directly and reveal nothing
  about the label word, the seed offset, the window span or the reserved byte.
  **(drift)**
- The chained mask reads the previous entry's settled tick and amount, so the
  decode is strictly sequential and a single missed entry desynchronises every
  entry after it. **(trap)**
- The filler lines appended to each opening block are invisible to the block
  check, which reads only the capture ordinal, the block ordinal and the
  declared width. **(trap)**
- The payload rotation and the block permutation are likewise invisible to the
  block check. **(trap)**
- Every flagged capture indexes its unit words through another capture's published word
  table, rotated, so the corpus cannot be read one file at a time. **(trap)**
- A reversal entry cancels the earliest still uncancelled entry of its kind
  recorded by that unit, not the latest one, and an unmatched reversal is
  promoted to an ordinary entry of its own mark. **(focal)**
- Identity is derived from a register of openings, closings and successors,
  including a self successor row that is held at its opening charter rather
  than chased. **(drift)**
- The charter relation is coupled: every charter's stock depends on every other
  charter's settled flow, so a unique stable assignment has to be solved for.
  **(focal)**
- One window in the schedule is degenerate, its first tick above its last, and
  admits no entry at all. **(drift)**
- One window is marked dead and admits no entry even though its bounds are
  ordinary. **(drift)**
- Each charter holds a running allowance the size of its cap. Settled entries
  draw on the allowance of the charter they serve one at a time in walk order,
  an entry draws what is left when the allowance cannot cover it, and the part
  it cannot draw is surplus carried to the reconciliation residual. Reversal
  matching finishes first, so a cancelled entry never draws. **(focal)**
- The first tick of every live window renews each allowance to its full size.
  The renewal sentence sits in the engine rules, the allowance size in the
  charter scale note, the window bounds in the tick schedule and the walk order
  in the reversal rules. **(focal)**
- Every calibration control, the header seal and the reconciliation identity
  stay green under a wrong allowance reading, because none of them reads a
  settled amount. **(trap)**

## Load-bearing work

The settlement is a serial chain of fourteen stages. Stage k consumes stage
k minus one's exact output; there is no stage that can be skipped and recovered
from later.

1. Read every capture, parse its header, and reduce the overstated frame count
   by the bias the capture ordinal implies.
2. Restate the line order inside each block, then drop the filler lines from
   the opening block and concatenate the blocks in ordinal order.
3. Unwrap the doubled reserved byte, lift the block mask, lift the chained
   mask, lift the label mask, undo the payload rotation, set the flipped block
   straight, unpack the twelve byte payload and verify its check.
4. Restore the ticks from their second differences, read every unit index
   against the right word table, and settle every repeated slot against the
   entry it inherits from.
5. Canonicalise identity from the register: chase successors, drop retirements,
   adopt the successor's charter on a merge, hold a self successor row at its
   opening charter.
6. Filter by the live windows, ignoring the dead one and the degenerate one.
7. Match reversals against the earliest still uncancelled entry of their kind,
   promoting any reversal that finds none, walking by tick then capture ordinal
   then entry ordinal.
8. Walk the settled entries in walk order and let each draw on its charter's
   allowance, renewing every allowance at the first tick of each live window,
   then total the drawn amounts and ticks per unit and per kind.
9. Solve the coupled charter relation exactly for the unique stable stock
   assignment.
10. Assign every surviving unit a cadence class from its settled tick total.
11. Compute the upkeep target from the charter baselines.
12. Find the one bench subset whose upkeep meets that target exactly.
13. Reconcile: the residual is the decoded total less the settled total less the
    dropped total.
14. Emit the ten artifacts.

The two convergence points are stage seven, which consumes the exact surviving
set stage six produced, and stage twelve, which consumes the exact target stage
eleven produced from the baselines stage five fixed.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app`.
`tests/test_output.py` registers one `@criterion` check per graded property, each
with its weight, and a check passes when that property holds.
`tests/judge.toml` holds the judged criteria. `tests/reward.toml` gives each
channel half of the reward: the tests weigh 0.5 divided by their positive total
of 158 and the judge weighs 0.5 divided by its positive total of 17.

Channel A is the tests channel, `tests/test_output.py`: 42 checks, 38 positive
weighing 158 and four negative weighing minus twenty. Every graded document is
compared whole, and a failing check prints the first path where the produced
document and the settled one part.

- Six shipped tests at weight 1: `format_program_delivered`,
  `instance_report_serialization`, which requires the example report's
  serialization on the four instance reports, and the four instance tests
  `instance_scenario_visible`, `instance_perf_report`,
  `instance_recommendations` and `instance_data_quality`.
- Two held-out tests at weight 1: `record_derivation_matches`, which compares
  every recovered value, rejected candidate, control figure and the settling
  pass count in the record written on the fresh deep chain set with that set's
  calibration slice, and `format_writes_only_named_reports`, which requires the
  report directory of a fresh run to hold the nine named reports and nothing
  else.
- Every fresh capture set draws its own eleven quantities from the published
  candidate ranges, so a program that carries the shipped values decodes none
  of the fresh sets.
- Twelve trap tests at weight 5, one per wire transform, each on a fresh capture
  set whose amounts are drawn forty times heavier so the allowances bind:
  `trap_sealed_inverse`,
  `trap_chained_inverse`, `trap_stepped_inverse`,
  `trap_drifted_inverse`, `trap_woven_inverse`,
  `trap_echoed_inverse`, `trap_flipped_inverse`,
  `trap_padded_inverse`, `trap_shadowed_inverse`,
  `trap_spun_inverse`, `trap_aliased_inverse`,
  `trap_warded_inverse`.
- Sixteen generalisation tests at weight 5 over fresh heavy capture sets, three of
  them plain sets graded on one cadence report each and thirteen mutated sets:
  `general_scenario_peak`, `general_scenario_steady`, `general_scenario_latency`,
  `general_deep_identity_chain`, `general_charter_cap_surplus`,
  `general_empty_charter`, `general_window_boundary_shift`,
  `general_degenerate_window_live`, `general_dead_window`,
  `general_reversal_density`, `general_population_scale`,
  `general_baseline_scale`, `general_reversal_tiebreak`,
  `general_cadence_partition`, `general_fixpoint_new_unit`,
  `general_donor_table_rotation`.
- Two mutation tests at weight 5, each staging a base capture set and a copy
  with one governed input changed: `mutation_cadence_modulus_moves_only_classes`
  changes the cadence modulus, so only the cadence classes move and every
  settled amount stays put; `mutation_window_split_moves_only_amounts` splits
  the live window holding the first short draw at that tick, so the admitted
  set and every cadence class stay put while the drawn amounts move.
- Four negative detectors at minus five each:
  `negative_hardcoded_sample_answers`, `negative_filename_dependent_behaviour`,
  `negative_reads_supplied_answer_data_at_runtime`,
  `negative_rebinds_verifier_dependencies`.

Channel B is the judge channel, `tests/judge.toml`, batched: 11 judged criteria,
positive total 17, negative total minus 8. Five positive instruction following
criteria at weight 1 carry the constraint total of 5. Three conduct criteria at
weight 3 ask whether the run built its own input for each reading the
allowance rules turn on and checked its program against it. One criterion at
weight 3 grades the shape of the delivered code. Two criteria are negative: a
write outside `/app/out` and a false claim that every control reproduced. The
free total is zero.

### Observable partition

Channel A asserts, and Channel B may never mention: the capture count, the
entry total, the settled total, every unit's charter, tick total, amount total,
cadence class and per kind totals, every cadence class report's member list and
amount total, every charter's stock, the settled total, the decoded total, the
reversal count, the promoted reversal count, the upkeep target, the bench set,
the bench upkeep, the residual after bench, the retired drop count, the off
window drop count, the dropped amount total, the decoded amount total, the
settled amount total, the conservation residual, the presence of the delivered
program, the byte serialization of the four instance reports, the derivation record's recovered values, rejected candidates,
control figures and settling pass count, and the listing of the report directory.

Channel B asserts, and Channel A never reads: the ordering and procedural
rules the run followed while it worked, the inputs the run built for itself
to check its allowance reading, the honesty of its closing claim about the
controls, and the shape of the delivered code.

The two lists are disjoint.

## Root cause

The shipping build's serializer treated its transform parameters as compile
time constants and never wrote them into the captures. The settlement engine
treated its cadence modulus and upkeep target scale the same way. The
calibration slice was published as a compatibility aid: it names the candidate
range of each quantity and publishes one control figure per quantity, ordered so
that each figure is fixed by the quantities pinned by the figures ahead of it
together with one further quantity. On the shipped slice exactly one value of
that further quantity reproduces the published figure, so the eleven quantities
are recoverable in that order and in no other. A capture set with fewer
transforms live can leave several values reproducing a figure; the engine's
value is always among them.

## Solution shape

A single reusable program at `/app/out/optimize.py` that takes the capture
directory as its first argument and the report directory as its second. It
discovers its inputs by content rather than by name, recovers the eleven
quantities against the published controls, runs the fourteen stage settlement,
and writes the eight settlement reports, one of which is the reconciliation
report, and the derivation record beside them. It uses the Python standard
library only and exact
rational arithmetic throughout.

## Ordered plan

1. Read the format note and the engine rules, and enumerate the candidate range
   of every quantity into the derivation record before any program exists. This
   earns R1.
2. Parse the two captures whose flag word is zero, confirm the base payload
   layout against them and begin /app/out/optimize.py on that layout. This
   earns `format_program_delivered` once the program compiles.
3. Recover the frame bias limit against its control, then the weave seed offset,
   then the reserved byte, then the drift modulus, then the label index, then
   the spin modulus, then the shadow pad base, then the alias donor shift, then
   the echo window span, each against the next control in the published order,
   appending every rejection with its falsifier at the moment of discard. This
   earns R2, R3 and `record_derivation_matches`.
4. Decode every capture through the full inverse pipeline.
5. Canonicalise identity from the register and record the number of settling
   passes.
6. Filter by the live windows and match reversals against the earliest still
   uncancelled entry of their kind. This earns `instance_scenario_visible`.
7. Walk the settled entries against the charter allowances, renewing them at
   every live window's first tick, and build inputs that overrun one allowance,
   cross a renewal and cancel an entry that would have drawn. This earns R7, R8
   and R9, and with step 4 the twelve trap tests.
8. Solve the coupled charter relation exactly with a rational facility rather
   than binary floating point. This earns R4 and `instance_perf_report`.
9. Recover the cadence modulus and the upkeep target scale against their
   controls, partition the units and find the exact bench subset. This earns
   `instance_recommendations`.
10. Reconcile and emit in the example report's serialization. This earns
    `instance_data_quality`, `instance_report_serialization`, the sixteen
    generalisation tests and the two mutation tests.
11. Empty the report directory of the eight reports and the record, rebuild them
    in one clean run leaving the program in place, and keep the program in
    named stages. This earns R5, R11 and `format_writes_only_named_reports`.

## Pitfalls

- Reading the two zero flag captures and assuming the rest are the same.
- Inverting the transforms in the order the format note lists them rather than
  the order the pipeline applies them.
- Trusting the block check to catch a missing filler line, a rotated payload or
  a permuted block; it reads none of them.
- Decoding entries independently; the chained mask makes the decode sequential.
- Reading a capture's unit words against the published word table when its flag
  word says the donor ring applies.
- Treating a reversal as an undo of the entry before it.
- Dropping an unmatched reversal instead of promoting it.
- Chasing a self successor row instead of holding it at its opening charter.
- Admitting entries from the dead window or the degenerate window.
- Substituting repeatedly into the charter relation instead of solving it.
- Using binary floating point anywhere in the settlement.
- Holding each entry at the cap on its own instead of drawing on a running
  allowance; the shipped captures never exhaust an allowance, so the shipped
  reports agree under both readings.
- Keeping one allowance for the whole walk instead of renewing it at every live
  window's first tick.
- Letting an entry draw before reversal matching and refunding it when it is
  cancelled, which leaves a later entry short.
- Drawing on the opening charter's allowance instead of the charter the entry
  settles under after the identity chase.
- Fixing the eleven recovered quantities as literal constants in the delivered
  program; every fresh capture set draws its own values from the published
  ranges.

## Provenance

```yaml
uuid: 4f1c7a92-6d3b-4e58-9a01-2c8b5de73401
instance_id: match-replay-desync-audit
task_name: terminal-bench/match-replay-desync-audit
fix_patch_sha256: faaa3a08bd1d5759bd804537c5c8a26a40484e6c177638f2f73dcc5b81bb051c
solve_py_sha256: f4603aa38eac03b1a97556893a213ecdfdfc147c530a7e4c3345242c24d477d8
language: python
```
