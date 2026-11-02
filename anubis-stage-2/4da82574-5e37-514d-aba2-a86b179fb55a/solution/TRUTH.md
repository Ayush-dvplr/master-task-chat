# TRUTH.md - 4da82574-5e37-514d-aba2-a86b179fb55a

## Defect

The `bcrep` custody replay engine ships inside `environment/data/project.zip`
in the state the facility currently runs it. It imports, runs to completion,
passes its own suite exactly as it shipped, and publishes a full set of
plausible documents that are wrong. Twenty two defects sit across eleven
modules and interact through one shared spine: ingestion, canonical order,
checkpoint selection and restoration, window construction, dependency closure,
transitions, compensation, carry settlement, the re offer rounds and
publication. The agent has to find them from the working papers, repair the
shipped source in place, deliver the repaired archive, and republish the
epoch.

1. (focal) `src/bcrep/window.py` opens the window at the restored watermark
   rather than one past it, so the event already folded into the checkpoint
   is applied a second time. Defeats `shipped_boundary_record_exact` and
   fires `negative_watermark_position_replayed_again`.
2. (focal) `src/bcrep/replay.py` quarantines a compensating event whose target
   stands behind the restored checkpoint as `CMP-NOTARGET` rather than
   resolving it against the whole canonical history. Defeats
   `shipped_reversal_record_exact` and fires
   `negative_compensation_target_sought_in_the_window`.
3. (focal) `src/bcrep/replay.py` hardcodes the re offer round ceiling at one
   rather than reading the revalidation round ceiling out of the board memo.
   Defeats `shipped_rounds_record_exact` and fires
   `negative_pending_queue_offered_once`.
4. (focal) `src/bcrep/compensation.py` reverses the balances and the
   allotments and leaves the derived counter of the reversed kind where it
   stood. Defeats `shipped_settlement_record_exact` and fires
   `negative_reversal_left_the_derived_counters`.
5. (drift) `src/bcrep/window.py` closes the window on the requested end
   position, which is the reading a closed range would take. Defeats
   `shipped_boundary_record_exact` and fires
   `negative_end_boundary_included`.
6. (trap) `src/bcrep/derived.py` binds the parsed checkpoint body straight
   into the working state rather than copying it, so one replay leaks into
   the next and the reconciliation digest moves. Defeats
   `shipped_boundary_record_exact`.
7. (trap) `src/bcrep/ordering.py` sorts on sequence and stamp alone, so the
   kind rank, the tie break key and the event identifier settle nothing.
   Defeats `shipped_canonical_order_exact`.
8. (trap) `src/bcrep/ordering.py` ignores the lodging source the provenance
   ledger supplies for a supplement record whose `source` field is empty.
   Defeats `shipped_canonical_order_exact`.
9. (focal) `src/bcrep/depends.py` reports a dependency already folded into
   the restored checkpoint as `DEP-MISSING`. Defeats
   `shipped_closure_record_exact` and fires
   `negative_checkpoint_dependency_called_missing`.
10. (trap) `src/bcrep/compensation.py` lets a second compensating event
    reverse a target that already sits in the reversed ledger. Defeats
    `shipped_reversal_record_exact` and fires
    `negative_target_reversed_twice`.
11. (drift) `src/bcrep/compensation.py` computes the derived reversal by
    dividing in binary floating point and rounding halves to even, which is
    what the language builtin does. Defeats
    `shipped_reversal_record_exact`.
12. (focal) `src/bcrep/derived.py` divides the spill by a constant rather
    than by the per class carry quantum on the live workbook sheet. Defeats
    `shipped_settlement_record_exact` and fires
    `negative_carry_quantum_defaulted`.
13. (drift) `src/bcrep/normalise.py` reads `station_register_current.csv`,
    which carries later lodges of the same keys with drifted classes.
    Defeats `shipped_parameter_layer_exact`.
14. (drift) `src/bcrep/replay.py` offers the pending queue in canonical order
    rather than by the five level ladder in the directive, and carries no
    ladder key at all, so the region rank has to be taken from the frozen
    register the way stage r12 says. Defeats `shipped_rounds_record_exact` and
    fires `negative_queue_offered_in_canonical_order`.
15. (trap) `src/bcrep/reading.py` pairs workbook sheet names with worksheet
    parts by position. The first sheet's relationship points at the second
    part, so the live sheet is published under the other sheet's name.
    Defeats `shipped_parameter_layer_exact`.
16. (trap) `src/bcrep/reading.py` inflates the memo's FlateDecode streams but
    reads every string as a line of its own. The resolutions adopted at
    sitting 7 are kerned TJ arrays, so their fragments parse as nothing and
    the earlier sittings govern: round ceiling 7, the earlier implausible
    ceiling and the earlier floor. Defeats `shipped_parameter_layer_exact`.
17. (trap) `src/bcrep/transitions.py` evaluates every predicate in the
    argument order first lodged and treats every known form as active. The
    register reorders `allotment_below` at revision 6 and retires
    `no_pending` at revision 7. Defeats `shipped_rounds_record_exact`.
18. (trap) `src/bcrep/depends.py` finds cycle members with a depth first walk
    that marks only the path above a back edge, so a member reached through a
    finished node is missed. Defeats `shipped_closure_record_exact`.
19. (trap) `src/bcrep/publish.py` keys the archive and the ceiling history by
    their natural keys, so a row lodged twice counts once in `archive_rows`
    and in `historic_ceiling_total_cu`. Defeats
    `shipped_boundary_record_exact`.
20. (drift) `src/bcrep/compensation.py` takes the reversal scale from the
    class the station carries at the frozen revision rather than at the
    revision of the target record. Defeats `shipped_reversal_record_exact`.
21. (trap) `src/bcrep/checkpointing.py` never tests a body's applied ledger
    against its watermark, so it selects a sealed checkpoint whose ledger runs
    past its watermark in the canonical order. Defeats
    `shipped_boundary_record_exact`.
22. (quiet) `src/bcrep/ordering.py` merges supplement rows lodged for a later
    epoch under the identifier prefix `data_lineage.md` names. The shipped
    epoch carries none; every minted epoch does. Defeats the three minted
    epochs.

The reference is Python on the 3.12 series, standard library only. Grading
runs on two channels: `tests/test_output.py` grades the delivered documents
and the delivered package against a reference chain the verifier owns, and
`tests/judge.toml` grades the diagnosis, the tool use and the reported
findings. `tests/reward.toml` combines the two channels into the one reward,
giving each channel half of the final value.

Out of bounds: rewriting the engine from scratch rather than repairing the
shipped source, which rubric R1 catches;
baking this epoch's values into the delivered package, which the ten
minted epoch `package_*` tests catch, since each minted epoch carries values
of its own and those tests hold 50 of the 74 positive test points;
`negative_hardcoded_sample_answers` adds a penalty when such a package
produces no usable output on any minted epoch, and
`negative_package_ignores_its_input` adds one when it emits a single fixed
final state other than the shipped epoch's for two different minted epochs,
and stands down when that fixed state is the shipped epoch's; carrying the
shipped reason code catalogue inside the package, which the minted epochs catch because
each words every reason afresh in its catalogue; substituting the
paper directory the package is pointed at for one whose answers the archive
already carries, which the paper directory digest guard inside `_drive`
catches and which the reference pinned before the package runs defeats in any
case; reading a corpus
other than the one the data option names, which
`negative_reads_training_corpus_at_runtime` catches; behaving
differently under a different directory name, which
`negative_filename_dependent_behaviour` catches; producing
different bytes on two runs over one directory, which
`negative_nondeterministic_output` catches; fabricating the two
digests, which `shipped_settlement_record_exact` and the three
`package_eval_publication_exact`, `package_challenge_publication_exact` and
`package_probe_publication_exact` tests catch, since `run_manifest.txt` is
compared byte for byte in each; and editing the shipped suite, which
`delivered_package_shape` catches.

## Load-bearing work

The graded deliverables are the 24 paths in `task.toml`:

- `/app/out/package.zip`
- `/app/out/repair_report.json`
- `/app/out/selftest.json`
- `/app/out/unit_normalisation.json`
- `/app/out/alias_resolution.jsonl`
- `/app/out/canonical_order.csv`
- `/app/out/quarantine_ledger.csv`
- `/app/out/checkpoint_selection.json`
- `/app/out/replay_window.json`
- `/app/out/dependency_closure.json`
- `/app/out/checkpoint_reconciliation.json`
- `/app/out/transition_log.jsonl`
- `/app/out/compensation_register.csv`
- `/app/out/derived_counters.csv`
- `/app/out/eligibility_passes.json`
- `/app/out/final_state.json`
- `/app/out/derived_index.jsonl`
- `/app/out/equivalence_report.json`
- `/app/out/state_at_event.json`
- `/app/out/bounded_replay.json`
- `/app/out/defect_register.md`
- `/app/out/verification_notes.md`
- `/app/out/run_manifest.txt`
- `/app/out/summary.json`

`/app/out/package.zip` carries `pyproject.toml` at the archive root, the
`src/bcrep` source tree holding all fourteen modules, and the shipped `tests`
directory byte for byte, which has to pass against the delivered source. The remaining twenty three documents are the epoch
republished: the preparation record, the boundary record, the replay record,
the settlement record, the repair record, the manifest and the summary. Each
is fixed in header line, column order, row order, key names and value types
by `output_schema_reference.md`, and in encoding, line endings, key ordering,
indentation and trailing newline by `serialisation_and_digest_contract.md`.
The two digests in `run_manifest.txt` are taken last, over the bytes already
written.

Out of bounds by design: the agent never sees a seed, and never needs a
value that is absent from `environment/data/`.
Every control value the chain consumes is written into one of the 57
working papers.

## Verification

`tests/test.sh` hardens the verifier and hands over to rewardkit, writing no
reward itself. rewardkit imports `tests/test_output.py`, runs every registered
criterion, and adds the weight of each one that returns true; it reads
`tests/judge.toml` and adds up that file's criteria the same way.
`tests/reward.toml` then gives each channel half of the final value, dividing
each channel's weighted sum by that channel's positive total.

Channel A declares 35 criteria: 20 positive summing to 74 and 15 negative summing to -57, each weight carried on its own `criteria.<name>(weight=W)` registration. Channel A takes half the reward, so its share runs -0.385 to 0.500, and the whole reward runs -0.460 to 1.000.

Positive tests:

- `package_challenge_publication_exact` (+5)
- `package_challenge_replay_exact` (+5)
- `package_challenge_window_exact` (+5)
- `package_eval_preparation_exact` (+5)
- `package_eval_publication_exact` (+5)
- `package_eval_replay_exact` (+5)
- `package_eval_window_exact` (+5)
- `package_probe_publication_exact` (+5)
- `package_probe_replay_exact` (+5)
- `package_probe_window_exact` (+5)
- `shipped_boundary_record_exact` (+3)
- `shipped_canonical_order_exact` (+3)
- `shipped_closure_record_exact` (+3)
- `shipped_parameter_layer_exact` (+3)
- `shipped_reversal_record_exact` (+3)
- `shipped_rounds_record_exact` (+3)
- `shipped_settlement_record_exact` (+3)
- `delivered_documents_present_and_parse` (+1)
- `delivered_package_shape` (+1)
- `shipped_settled_documents_exact` (+1)

Negative tests:

- `negative_compensation_target_sought_in_the_window` (-5)
- `negative_filename_dependent_behaviour` (-5)
- `negative_pending_queue_offered_once` (-5)
- `negative_reads_training_corpus_at_runtime` (-5)
- `negative_reversal_left_the_derived_counters` (-5)
- `negative_watermark_position_replayed_again` (-5)
- `negative_carry_quantum_defaulted` (-3)
- `negative_checkpoint_dependency_called_missing` (-3)
- `negative_end_boundary_included` (-3)
- `negative_hardcoded_sample_answers` (-3)
- `negative_nondeterministic_output` (-3)
- `negative_package_ignores_its_input` (-3)
- `negative_queue_offered_in_canonical_order` (-3)
- `negative_rebinds_verifier_dependencies` (-3)
- `negative_target_reversed_twice` (-3)

Channel B declares 31 criteria: 27 positive summing to 93 and 4 negative summing to -14. Five are
instruction following constraints and lead the file. R6, R7 and R8 grade the
demonstrations the agent printed of the package properties and R25 holds the
agent to the interpreter and packages the image shipped; those four are
conduct criteria labelled agent behavior. Every criterion names a concrete
paper, field, code or rule of this epoch. A model that never opened the
workbook, the memo or the directive can still earn R1, R9 and R10, but earns
none of R3, R11, R12, R18 and R23, which need a value or rule only those papers
carry. The four negative criteria fire on named naive paths: a rescinded or
superseded memo resolution, the superseded scale table quoted as in force in
the final message, a run that reaches into the grading directory, and a
verification step reported as passed that the trajectory never carries. No negative criterion repeats a negative test, so no
single wrong reading is charged twice across the two channels.

No criterion reads an observable a deterministic test already decides. Every
fact that lands in a published document is graded by the tests alone; the
rubric grades the diagnosis, the tool use, the verification the agent ran and
whether it closed with the report the task asks for. Where a rule could be
settled by either layer, the assertion owns it, because an assertion returns
the same verdict every run and a judge does not.

The two channels are disjoint. Channel A grades the delivered bytes and the
behaviour of the delivered package. Channel B grades the trajectory, the tool
use and the final message, and never a value inside a delivered document. The
one criterion that does open the delivery reads the repaired source for its
maintainability, which no assertion decides and which leaves the published
bytes identical either way.

## Root cause

**The watermark is a processed position.** A checkpoint that carries
watermark N stands after the event at canonical position N. The first
candidate the window can replay is N plus one. Reading the watermark as the
next position to replay applies one event twice and every counter and balance
it touched carries the doubling forward.

**The range is half open.** Start is included and end is excluded. The board
memo restates it and `spec_stage_r06_replay_window.md` states it. A closed
reading admits one extra event at the far end of every window, including the
bounded window and the from scratch comparison.

**Compensation is not adjacency.** A compensating event names its target
through the link register, and the target is resolved against the whole
canonical history. The target may stand behind the restored checkpoint. Its
station, programme, kind, class and normalised quantity are read off the
canonical record; the target is never replayed again in order to reverse it.
A target is reversed exactly once however many compensations name it, and the
reversal moves the derived counter of the reversed kind as well as the
balances.

**Eligibility is not settled once.** An event whose predicate is false waits
in the pending queue, which is part of the state and travels inside a
checkpoint body. A compensation later in the window changes the state the
predicate reads, so the queue is offered again after the window is exhausted,
in the order the directive ladder gives, until a round admits nothing or the
memo ceiling is reached. This epoch is built so the ceiling binds.

**A dependency behind the window is satisfied.** It is already folded into
the restored checkpoint. Calling it missing quarantines events the checkpoint
has already accounted for, and the quarantine cascades into the counters.

**Exactness.** Every published quantity is an integer in credit units and
every ratio carries twelve decimal places. The two rounding points are the
class conversion in stage r01 and the derived reversal in stage r10, both
half away from zero on an exact rational. The epoch carries a reversal whose
exact value lands on a half with an even whole part, which is where the
language builtin and the documented rule part company.

**Three papers are not plain text.** The class conversion factors, the class
reversal scales, the per class carry quanta and the per revision ceilings
live on one of two workbook sheets, and the sheet in force is chosen by
matching an epoch key cell that sits under a header row, below a decoy
`epoch_key_prior` cell. A sheet reaches its worksheet part through its
relationship, and the first relationship points at the second part. The round
ceiling, the implausible ceiling and the settlement floor live in the memo,
whose content streams are compressed and whose sitting 7 resolutions are
kerned TJ arrays; its resolutions carry sitting numbers and its rescinded
lines carry no force. The ladder and the two closure rules live in the
directive. The carry quantum in force appears nowhere else; the legacy scale
table carries only superseded ones.

**One checkpoint is usable.** Only CKP-0008 carries the state the forward
pass reached. Every other lodged body is the state the same pass reaches
under the decoy readings, legacy quantum, half to even rounding, the current
register and arrival order, with a digest of its own, so no body hands over
a later state and skipping the revision filter selects a plausible wrong
one. CKP-0163 passes every other test, but its applied ledger names an event
the canonical order puts after its watermark. In every minted epoch CKP-0241
fails that ledger test and the end boundary test together, so the order the
six tests run in decides the reason it is rejected under. The archive counts are read off
the lodged bodies for the same reason.

**The registers carry their own history.** The predicate register reorders
the arguments of `allotment_below` at revision 6 and retires `no_pending` at
revision 7. The reversal scale is the class the frozen register carried at
the target record's revision. The region on the ladder is the frozen
register's, which for the two drafted stations ST-0058 and ST-0145 differs
from the roster and the topology, and that difference decides which events
the round ceiling cuts off. A cycle is any path of edges back to an event,
however a walk meets it. A row lodged twice counts twice.

**The reference is a second implementation.** The chain the delivered package
is graded against is written from the stage papers, not from the package
source, and shares only the format plumbing with it: the readers, the writers,
the digest, the rounding and the ratio. This is what gives the oracle run its
meaning. A reference copied from the package it grades cannot disagree with
it, so the run would read 1.000 whatever the papers said, and a divergence
between a paper and the engine would never surface. Two implementations
written apart agree only when both are right. They are held to byte identity
on the shipped epoch, on the three minted epochs and on every one of the named
wrong readings the negative detectors rebuild.

**Delivered code is contained.** Every run of the delivered package or its
suite leads a session of its own and is reaped, together with any process
left running under the demoted uid, before the check that started it
returns, and the directory the reference is written to is closed to that
uid.

**Red lines.** Every value needed to solve the task appears in
`environment/data/` or follows from its documented rules. The verifier does
not grade SQLite container byte layout; it reads the rows.

## Solution shape

1. Extract `project.zip` into a working tree.
2. Apply one targeted edit per catalogued defect, asserting each anchor
   matches its module exactly once before it is applied.
3. Write the repaired tree back out as `/app/out/package.zip` with fixed
   archive timestamps so the archive is reproducible.
4. Drive the repaired package over the working papers through
   `python3 -m bcrep --data /app/data --out /app/out`.
5. Confirm the shipped suite still passes on the repaired tree.

## Ordered plan

1. Read `00_open_this_first.txt`, the contract, the lineage map and the
   readings not in force. Earns R1 and R2.
2. Open the workbook, the memo and the directive with the standard library
   and print the rows and lines each control value comes from. Earns R12,
   R11 and R23, and avoids R26 and R27.
3. Extract the package and read the fourteen modules against the fourteen
   stage papers, including the branches this epoch never reaches. Earns R1
   and R4.
4. Work the preparation stages first: the frozen register, the aliases, the
   provenance fallback and the five level canonical order. Earns R16, R17 and
   R21.
5. Work the boundary stages: checkpoint selection with its six rejection
   reasons, restoration by copy, the half open window. Earns R9, R20, R22 and
   R24.
6. Work the closure and compensation stages: the checkpoint satisfied
   dependency, the cross boundary target, the single reversal, the derived
   counter movement, the exact rational rounding and a cycle test that finds
   every member however the walk meets it. Earns R10, R13, R14, R15, R19 and
   R31.
7. Work the settlement and round stages: the per class carry quantum and the
   ladder ordered re offer rounds. Earns R12 and R18.
8. Deliver the archive, run the package twice over one directory and once
   over a renamed copy, and confirm the paper directory is untouched. Earns
   R6, R7 and R8; leaving the paper directory untouched is graded by rubric R5
   and by the tests.
9. Report the live sheet and key cell, the selected checkpoint, the reason
   code counts, the round count, the void compensations and the carry quantum
   governing the largest settled balance. Earns R3.

## Pitfalls

- Taking the workbook sheet by name or by position rather than by the epoch
  key cell. Fails `shipped_parameter_layer_exact`.
- Taking the round ceiling from a rescinded line or an earlier sitting.
  Fails `shipped_rounds_record_exact` and rubric R26.
- Quoting `legacy_scale_table.csv` as the scales in force. Fails
  `shipped_parameter_layer_exact` and rubric R27.
- Leaving the carry quantum as a constant. Fails
  `shipped_settlement_record_exact` and fires
  `negative_carry_quantum_defaulted`.
- Reading the watermark as the next position to replay. Fails
  `shipped_boundary_record_exact` and fires
  `negative_watermark_position_replayed_again`.
- Searching for a compensation target inside the window alone. Fails
  `shipped_reversal_record_exact` and fires
  `negative_compensation_target_sought_in_the_window`.
- Offering the pending queue once. Fails `shipped_rounds_record_exact`
  and fires `negative_pending_queue_offered_once`.
- Offering the pending queue in canonical order. Fires
  `negative_queue_offered_in_canonical_order`.
- Reversing the balances and leaving the counters. Fires
  `negative_reversal_left_the_derived_counters`.
- Calling a checkpoint satisfied dependency missing. Fires
  `negative_checkpoint_dependency_called_missing`.
- Replaying the end position. Fires `negative_end_boundary_included`.
- Reversing one target twice. Fires `negative_target_reversed_twice`.
- Rounding the derived reversal with the language builtin. Fails
  `shipped_reversal_record_exact` and `package_challenge_replay_exact`.
- Reading `station_register_current.csv`. Fails
  `shipped_parameter_layer_exact`.
- Publishing a ratio at a different number of places or publishing a negative
  zero. Fails `delivered_documents_present_and_parse`.
- Fabricating the two digests. Fails `shipped_settlement_record_exact`
  and the three publication tests `package_eval_publication_exact`,
  `package_challenge_publication_exact` and
  `package_probe_publication_exact`.
- Delivering a package that reproduces the shipped epoch on every input.
  Fails all ten minted epoch `package_*` tests;
  `negative_package_ignores_its_input` stands down on the shipped epoch and
  leaves that case to those tests.
- Pairing workbook sheet names with worksheet parts by position. Fails
  `shipped_parameter_layer_exact`.
- Reading the memo's kerned TJ arrays one fragment at a time. Fails
  `shipped_parameter_layer_exact` and rubric R26.
- Reading a predicate in the argument order first lodged, or a retired form
  as active. Fails `shipped_rounds_record_exact`.
- Ranking the ladder region off the roster or the topology. Fails
  `shipped_rounds_record_exact`.
- Finding cycle members with a walk that misses a member reached through a
  finished node. Fails `shipped_closure_record_exact`.
- Counting archive or ceiling history rows by key. Fails
  `shipped_boundary_record_exact`.
- Taking the reversal scale at the frozen class. Fails
  `shipped_reversal_record_exact`.
- Selecting a checkpoint whose applied ledger runs past its watermark, or one
  lodged above the frozen revision. Fails `shipped_boundary_record_exact`.
- Merging the supplement rows lodged for a later epoch. Fails every minted
  epoch test.
- Breaking the shipped suite while repairing. Fails `delivered_package_shape`.

## Provenance

```yaml
uuid: 4da82574-5e37-514d-aba2-a86b179fb55a
instance_id: 4da82574-5e37-514d-aba2-a86b179fb55a
task_name: terminal-bench/4da82574-5e37-514d-aba2-a86b179fb55a
fix_patch_sha256: e73ba4a4a052e465c70a73a09981ec300c424396212932706240cd90ea7020f2  # git diff from the project.zip tree to the repaired tree
solve_py_sha256: d76b3c8e0007880fc54f69181658ffe498e765b70e3edfc4837c1dff6a67f608
language: python
data_file_count: 57
artifact_count: 24
channel_a_positive_total: 74
channel_a_negative_total: -57
channel_b_positive_total: 93
channel_b_negative_total: -14
measured_oracle_test_channel: 1.000
measured_nop_test_channel: 0.000
measured_stub_test_channel: 0.000
measured_channel_note: >-
  The three figures above are the test channel alone. The judged channel is
  validated against the rewardkit 0.2.1 schema and never executed for these
  runs, because the oracle, nop and stub agents make no model calls and leave
  no trajectory, so no whole reward figure exists for any of them.
```
