# TRUTH.md - match-replay-desync-audit

## Defect

A turn-based strategy title shipped a build whose replay serializer applied a
menu of space-saving wire transforms to every capture it wrote. The header of
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
- The chained mask reads the stored tick and amount of the entry before it, 0
  and 0 for the first entry and after a `none`, so the decode runs in entry
  order. **(trap)**
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
   straight, unpack the twelve byte payload and verify its check. A payload
   with a lone reserved byte or of the wrong width reads as twenty four zero
   digits and decodes to `none`.
4. Restore the ticks from their second differences, a `none` entry counting
   as a stored 0, read every unit index modulo the length of the right word
   table, and settle every repeated slot against the entry it inherits from.
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
of 172 and the judge weighs 0.5 divided by its positive total of 17.

Channel A is the tests channel, `tests/test_output.py`: 46 checks, 42 positive
weighing 172 and four negative weighing minus twenty. Every check that compares
a produced document with its settled one compares it whole, except that on a
fresh capture set each scenario_visible comparison sets aside the capture count
and each unit's cadence class, the cadence modulus mutation test compares only
each unit's cadence class, and the flipped and warded trap tests sum the
retired and off window drop counts. A failing check prints the first path where
the produced document and the settled one part.

- Six shipped tests at weight 1: `format_program_delivered`,
  `instance_report_serialization`, which requires the example report's
  serialization on the four instance reports, and the four instance tests
  `instance_scenario_visible`, `instance_perf_report`,
  `instance_recommendations` and `instance_data_quality`.
- One held-out test at weight 3, `record_derivation_matches`, which compares
  every recovered value, rejected candidate, control figure and the settling
  pass count in the record written on the fresh deep chain set with that set's
  calibration slice, and one held-out test at weight 1,
  `format_writes_only_named_reports`, which requires the report directory of
  a fresh run to hold the nine named reports and nothing else.
- Every fresh capture set draws its own eleven quantities from the published
  candidate ranges, so a program that carries the shipped values decodes none
  of the fresh sets.
- Twelve trap tests at weight 5, one per wire transform, each on a fresh capture
  set at the shipped amount scale, where the generator asserts that every
  charter stays under its allowance under any reading, so a wrong allowance
  reading costs none of them:
  `trap_sealed_inverse`,
  `trap_chained_inverse`, `trap_stepped_inverse`,
  `trap_drifted_inverse`, `trap_woven_inverse`,
  `trap_echoed_inverse`, `trap_flipped_inverse`,
  `trap_padded_inverse`, `trap_shadowed_inverse`,
  `trap_spun_inverse`, `trap_aliased_inverse`,
  `trap_warded_inverse`.
- Four damage tests at weight 3, each on a fresh light capture set that plants
  undecodable payloads or wrapped unit indexes, and the generator asserts the
  reference decode reads them as the calibration notes say:
  `trap_zeroed_payload_inverse` (a payload with a lone reserved byte or the
  wrong width reads as zeros), `trap_carry_reset_inverse` (the chained mask
  restarts at 0 and 0 after a `none`), `trap_stepped_gap_inverse` (a `none`
  counts as a stored 0 in the stepped series) and `trap_index_lap_inverse`
  (the unit index is taken modulo the word table length).
- Sixteen generalisation tests at weight 5 over fresh capture sets, fifteen of
  them forty times heavier so the allowances bind and the tie-break set light so
  the walk order shows in the settled amounts, three of
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
weight 3 asks whether a Python reviewer would accept the delivered
`/app/out/optimize.py` as maintainable, judged on its names, function structure
and error handling. The oracle's `solve.sh` shows R7, R8 and R9 in a self-check
stage that builds three small inputs under `/app/out/selfcheck`, runs the
program on each, prints `check R7 ok`, `check R8 ok` and `check R9 ok`, and
removes the directory.
Two criteria are negative: a write outside `/app/out` and a false claim that
every control reproduced. The free total is zero.

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
controls, and the code quality of the delivered program.

The two lists are disjoint.

### One fact wrong

Tests channel points earned out of 172 by the oracle with one rule changed:

| rule read wrongly | tests earned |
|---|---|
| none (oracle) | 172 |
| each entry capped on its own, no running allowance | 97 |
| allowance never renewed at a window opening | 97 |
| allowance drawn from the opening charter | 97 |
| cancelled entry draws before it is cancelled | 97 |
| renewal only at windows opening strictly before the tick | 162 |
| off window drop checked before the retired drop | 161 |
| walk tie-break by entry ordinal before capture ordinal | 167 |
| reversal cancels the latest entry of its kind | 1 |
| one calibration note rule (zero payload, carry reset, stepped `none`, index modulo) | 169 |
| all four of those calibration note rules | 160 |
| shipped quantities carried as constants | 12 |

A wrong allowance reading costs fifteen of the heavy generalisation and
mutation tests and no trap test; a single calibration note rule costs its own damage
test.

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
   and R9, and with step 4 the twelve trap tests and the four damage tests.
8. Solve the coupled charter relation exactly with a rational facility rather
   than binary floating point. This earns R4 and `instance_perf_report`.
9. Recover the cadence modulus and the upkeep target scale against their
   controls, partition the units and find the exact bench subset. This earns
   `instance_recommendations`.
10. Reconcile and emit in the example report's serialization. This earns
    `instance_data_quality`, `instance_report_serialization`, the sixteen
    generalisation tests and the two mutation tests.
11. Empty the report directory of the eight reports and the record, rebuild them
    in one clean run leaving the program in place, and keep its names, function
    structure and error handling fit for a Python reviewer. This earns R5, R11
    and `format_writes_only_named_reports`.

## Pitfalls

- Reading the two zero flag captures and assuming the rest are the same.
- Inverting the transforms in the order the format note lists them rather than
  the order the pipeline applies them.
- Trusting the block check to catch a missing filler line, a rotated payload or
  a permuted block; it reads none of them.
- Decoding entries independently; the chained mask makes the decode sequential.
- Carrying the chained mask over a `none` entry instead of restarting it at 0
  and 0.
- Writing a payload with a lone reserved byte or the wrong width as `none`
  before the drift and chain stages instead of as twenty four zero digits.
- Treating every tick after a `none` entry as unknown; the `none` counts as a
  stored 0 and the series continues.
- Rejecting a unit index past the end of the word table instead of taking it
  modulo the table length.
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
solve_py_sha256: 20987612aa54950b4359ca484a4d06b46637ed5a3c42272ce8b3f5b7da1ce217
language: python
```
