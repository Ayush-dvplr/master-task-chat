# TRUTH.md - 65ba10c2-1913-5076-94a6-d8763828cf25

## Defect

The published operational ledgers of one shift of the Kestrel Point container
terminal were withdrawn after the vessel agents disputed them. The working
papers survive and the publication has to be recomputed from them. There is no
broken program to repair: the defect is that the derivation itself was never
written down anywhere but the specifications, and seventy six separate decisions
in those specifications each have a fluent wrong default that a careful engineer
reaches for.

The items below are the ones that decide the publication. Each is labelled with
what it is: focal when it carries most of the weight, drift when it is a quiet
divergence between two papers, trap when it is a shape that invites a wrong
reading.

(focal) The quay ration of stage Y13 is a damped cap and redistribute iterate
under a hard pass budget. Every pass computes a residual need, apportions the
unallocated pool across it, caps at the vessel slot ceiling, redistributes what
the caps freed inside the cross classification of berth and service group, damps
the move toward the aim by the workbook fraction, and rounds to whole crane
minutes before the next pass opens. On the shipped shift twenty six of the
thirty six pairings are still moving when the budget runs out; the other ten
stop early at RULE Y13.5a and are settled. A ration run to convergence, a ration
that rounds once at the end, and a ration that redistributes across the whole
pairing each disagree with the published one on every pairing.

(focal) Stage Y07 settles reserved capacity before free capacity. The free
capacity of the destination block is taken, the standing credit of every
reservation covering that block and slot whose service group differs from the
order's is withheld from it, and what remains is what the order may be placed
against. A block that shows free slots therefore refuses placements, and the
rung that catches them is the fifth of six.

(focal) Stage Y07 is stateful and is walked in canonical event order. Every rung
is judged against the yard as it stood immediately before that order, so a later
order can never change the state an earlier one was judged against.

(focal) The duplicate rung is the last rung, so the canonical member of a cluster
is the first member no earlier rung caught. A cluster whose first listed member
carries an unknown box has its second member as its canonical one.

(focal) Stage Y09 keeps the two movement streams separate. A landed confirmation
naming an order the ladder set aside records a contradiction and moves nothing.

(drift) A reservation whose quantity column carries the not supplied marker asks
for the whole opening free capacity of its block, and a reservation asking for
more than that free capacity withholds the free capacity and publishes the
excess as unmet.

(drift) The applicable revision of a register is the highest revision sequence
that survives the set aside rules, and three registers carry a set aside row
whose sequence is the highest of all: two vessel calls whose top revision is
withdrawn, one of which falls back to a lower revision while the other has
every revision withdrawn and so has no applicable call at all, ten mass
declarations whose superseded reweigh outranks the filed row of the same box,
and every source priority row at sequence three, which is retired.

(drift) `block_geometry_register.csv` carries a current, unretired geometry row
for `BLK-Y01` under this shift's identifier, and `yard_topology.xml` omits that
block. The topology is what says which blocks are in force.

(trap) A raised minute that falls exactly on a slot boundary belongs to the slot
that is closing. Minute 240 with two hour slots belongs to SL02.

(trap) A ready minute exactly equal to a vessel cutoff minute is inside the
cutoff. A placement at exactly the maximum legal tier is lawful. An equipment
unit that has carried exactly its allowance is inside it.

(trap) A mass declaration carrying the not supplied marker is published with a
mass of zero and a state of not_declared, and that box is excluded from every
mass total. Reading the marker as a declared zero puts it into the totals.

(trap) The admission ladder is printed in the order it is applied, which is not
the alphabetical order of its rung codes.

(trap) `box_class_supplement.csv`, `legacy_tariff_extract.csv` and
`shift_office_audit.db` govern nothing and `data_lineage.md` says so. The base
move charge comes from the live workbook sheet and not from the legacy tariff.

## Load-bearing work

The corpus is fifty nine working papers. Twenty are row bearing and every one of
them carries at least two hundred rows. Fifteen file formats appear.

Three papers are not plain text and carry values found nowhere else.
`quay_capacity_workbook.xlsx` is a real OOXML workbook of six sheets. Its live
sheet is the one whose cell B1 carries the shift reference that
`yard_topology.xml` declares. It issues the ration damping fraction, the
kilograms in one decitonne, the kilograms in one centner, the base move charge,
the teu factor of each iso length, the plug ceilings and a vessel slot ceiling
register. Across the shipped shift and the three minted shifts the live sheet
sits at file positions 3, 4, 2 and 5, at sorted ranks 2, 3, 4 and 5, and
carries four distinct names, so no fixed reading of position, position from the
end, sorted rank or name is right on more than one shift, and it is never the
first or the last sheet under either ordering.

`berth_operations_memo.pdf` is a real PDF of two hundred and sixty seven text
lines. It issues the ration pass budget, the ration minimum step, the dependency
protection depth, the rehandle surcharge ladder and a quay gang roster of two
hundred and sixteen rows. The pool a pairing rations is the smaller of the
declared berth window and the gang minutes that roster crews, so the memorandum
is load bearing twice over.

`stowage_ordering_directive.docx` is a real OOXML document. It issues the four
stowage ordering keys by key position, the class rank register and a bay
assignment register of three hundred and thirty six rows. The class rank
register and the order of the two middle ordering keys both change between
shifts, so a program holding either one is right on one shift and wrong on the
other three.

The ration damping fraction gates final state verification on its own: without
it every crane minute, every loaded box, every deferred box and every
republished charge in the publication is wrong, and it exists in no plain text
paper.

## Verification

Grading runs in a separate container with no copy of the agent corpus. The
verifier owns its corpus: it regenerates the shipped shift from its own seed,
recomputes the publication, and grades the delivered bytes against it.

The oracle is a second implementation, written from the fourteen stage
specifications and the two contract papers rather than from the grader. It
shares no code with the verifier's reference half, so on every stage the two
are able to disagree. Stage Y13, the one derivation of the shift that is not a
lookup, is decomposed differently on each side: the oracle apportions, trims
and redistributes through a per vessel offer record and a standalone
`redistribute_within_cell`, where the verifier carries the cell loop inline over
four parallel dictionaries. They are held to agree on all thirty nine documents
of all four graded shifts, and that agreement, rather than the oracle run on its
own, is what says the task is solvable as specified.

Three further shifts are minted from seeds the agent never sees, under a
strained quay profile, a wide profile and a sparse profile. The delivered
`yardledger.py` is run against each as an unprivileged subprocess through
setpriv, so submitted code cannot read the verifier module that holds the
reference pipeline and the seeds. The recomputed reference publication of every
graded shift is held in a root owned directory of its own rather than beside
the papers it was derived from, so a program that copies its working tree
instead of deriving anything finds nothing to copy. It is called the way its contract states it
is called and no other way: the graded run gives the two options in the reverse
order to the repeat run, and neither run creates the output directory, so a
program that takes the options in one order only, or that expects its output
directory to exist already, forfeits the whole program tier.

The positive total is 68 across three tiers. Three packaging checks at weight 1
give a floor of 4.4 percent. Five shipped checks at weight 3 cover what the
visible corpus alone can settle: the fourteen document stage spine, the state
family, the yard family, the vessel family and `publication_manifest.json`. Ten
program checks at weight 5 grade the delivered program on the three unseen
shifts. Nothing is gated on anything else. Each family is compared against the
publication its own papers entail, and the manifest carries its own weight
rather than sitting inside the spine set, so a document read the wrong way
costs the family it sits in and the manifest that digests it, and nothing more.
Measured on the shipped bytes: a delivery with one cent wrong in one row of
`deferred_containers.tsv`, and the manifest honestly digesting that row, scores
0.912 against the oracle's 1.000.

Sixteen negative checks carry weight -3 or -5, and they are disjoint by
construction: each one raises, and so stays silent, on the defect another one
owns, so a single wrong decision never charges more than one penalty.
`negative_filename_dependent_behaviour` takes its own run under the original
directory name and stands down when that run and the graded run already
disagree, so a program whose output is not a pure function of its input bytes
is charged once, by `negative_nondeterministic_output`, rather than twice. It
also raises, rather than returning the cheat verdict, when the renamed run
cannot complete, so a program that times out or exits non zero is not charged
for a defect it has not been shown to have. The
carried answers detector fires only when a minted run hands back the shipped
shift's own spine instead of the one its input entails, so a program that
derives from its input and still gets an unseen shift wrong forfeits the
program tier without being charged as a cheat. Eight are named wrong readings:
the ladder walked alphabetically, free capacity counted before the reserved
credit is withheld, the ration run to convergence, the ration rounded once at
the end, freed minutes redistributed across the whole pairing, a landed
confirmation overturning the ladder, an absent mass read as a declared zero, and
a boundary minute given to the opening slot. Each recomputes the shipped shift
with that one decision reversed and fires only when the delivered bytes match
the reversal, so a correct delivery escapes every one of them. The remaining
eight are the cheat detectors: `negative_hardcoded_sample_answers`,
`negative_reads_training_corpus_at_runtime`,
`negative_program_ignores_its_input`, `negative_nondeterministic_output`,
`negative_filename_dependent_behaviour`,
`negative_program_dirties_its_directories`,
`negative_rebinds_verifier_dependencies` and
`negative_manifest_digest_mismatch`. The eight named wrong readings are
`negative_alphabetical_ladder_order`,
`negative_free_capacity_before_reserved`,
`negative_ration_run_to_convergence`, `negative_ration_rounds_once_at_end`,
`negative_redistribution_across_the_pairing`,
`negative_confirmation_overturns_the_ladder`,
`negative_absent_mass_read_as_zero` and
`negative_slot_boundary_opens_the_slot`.

The judged channel in `tests/judge.toml` carries forty criteria, positive total
91 and negative total 19. Twenty nine read the trajectory, nine read the final
message, and two read the delivered program as a state change, R9 for its
fourteen named steps and R40 for its maintainability. No judged criterion
compares a delivered document against a reference publication, which is what
makes the two channels observable disjoint: the tests own the bytes, and the
judged channel owns the route taken to them and the quality of the program left
behind. `tests/reward.toml` halves each channel at 0.5 divided by each channel's
positive total, so the oracle reaches 1.0, an empty container 0.0 and the floor
is -1.0.

Nine of the forty read the final message, one for each of the nine items the
last paragraph of `instruction.md` demands be reported, so no promise the
instruction makes to the reader is graded by nothing that reads the reader's
answer. Across both channels the twenty one negatives group into twenty one
single membered triggering actions, none above the ceiling of 5: the test
channel prices a delivered program that dirties the directory it is pointed at,
and R35 prices the agent reaching into the shipped papers by hand, which is a
different act that the test cannot observe.

Measured on the shipped bytes by running every registered check against a
prepared workspace, tests channel only: the oracle scores 68 of 68 with all
sixteen negatives silent; an empty container scores 0; a stub holding the forty
declared paths as empty files earns `all_artifacts_exist` and fires
`negative_program_ignores_its_input`, netting -2 of 68, so faking the shape of
the delivery costs more than it earns; and a delivery with one cent wrong in one
row of `deferred_containers.tsv`, with the manifest honestly digesting that row,
scores 62 of 68, losing the vessel family and the manifest and nothing else. The
oracle and the verifier's reference half were also compared document by document
on all four graded shifts, including the four documents stage Y13 publishes, and
agree on every byte of all thirty nine.

## Root cause

The terminal never wrote its derivation down as code. Its rules live in fourteen
stage specifications, nine cross cutting policy papers and three office
documents, and the shift office relied on one superintendent to hold the
interactions between them. The two that matter most are invisible in any single
paper: reserved capacity has to be settled before free capacity at the moment
each order is judged, and the quay ration has to stop when its pass budget is
spent rather than when it settles. Both are stated, and both are stated in one
place each.

## Solution shape

Read the papers, then implement the fourteen stages in order with exact rational
arithmetic and no binary floating point. Read the load ordering keys out of the
directive by key position rather than assuming an order, and read the class
ranks out of it too; both change from shift to shift. Carry the yard as mutable state through
stage Y07 in canonical event order. Snapshot occupancy and reservation credit at
every slot close for stage Y11. Run the ration once per slot and berth pairing
for exactly the number of passes the memorandum allows, rounding at the end of
each. Take the digests last.

## Ordered plan

1. Read `readme_first.txt`, `terminal_contract_overview.md` and
   `data_lineage.md`, and list the fourteen stage specifications.
2. Read the three office documents and record every control value, selecting
   the workbook sheet by its key cell.
3. Build the canonical event set and the canonical event order.
4. Normalise masses and lengths, settle the vessel calls, materialise the
   opening yard.
5. Build the dependency graph and break its cycles.
6. Walk the admission ladder statefully, settling reserved capacity first.
7. Carry the state forward and snapshot it per slot.
8. Reconcile the planned and physical streams.
9. Derive rehandles and equipment usage from the state.
10. Publish capacity per block and slot.
11. Join the cutoffs to the yard state.
12. Run the quay ration and settle the load.
13. Close the accounts, check by identity, take the digests last.
14. Write `yardledger.py` to its contract and confirm two runs agree.

## Pitfalls

Reading the ladder rungs in alphabetical order. Counting free capacity without
withholding the reserved credit. Treating an absent reservation quantity as
zero. Picking the canonical cluster member before the earlier rungs are applied.
Giving a boundary minute to the opening slot. Taking the highest revision
sequence without first setting aside retired, future, withdrawn and superseded
rows. Letting a landed confirmation move a box the ladder set aside. Counting
rehandles from a source column rather than deriving them from the state history.
Reading the surcharge against the destination tier. Running the ration to
convergence. Rounding the ration once at the end. Redistributing freed minutes
across the whole pairing. Taking the base move charge from the legacy tariff.
Picking the workbook sheet by name or position. Assuming the stowage ordering
keys come in the order the shipped shift happens to print them. Rationing a
pairing over the declared berth window without capping it at the gang minutes
the roster crews. Working the cyclic components in the order a traversal
happens to find them rather than in ascending component key.

## Provenance

```yaml
uuid: 65ba10c2-1913-5076-94a6-d8763828cf25
instance_id: 65ba10c2-1913-5076-94a6-d8763828cf25
task_name: terminal-bench/65ba10c2-1913-5076-94a6-d8763828cf25
fix_patch_sha256: 5b1bb6358073dc521c67520958f1840fa1877c8e42a3de43aa20f24b15fcfbf1
solve_py_sha256: c13c0419fcc0dc38036f95f139d4c57ccb6d7fc341168cfb601cbd4c9f267fa3
language: python
category: data-processing
measured_oracle_reward: 1.0
measured_nop_reward: 0.0
verification_notes: >-
  every score here is a TESTS ONLY score, the test_output channel on its own
  before tests/reward.toml halves it; no judged channel score is claimed,
  because the judged channel is scored by an LLM and has no deterministic
  oracle value. The test channel registers 34 checks, positive total 68 and
  negative total 62; the judged channel carries 40 criteria, positive total 91
  and negative total 19; tests/reward.toml carries 0.5/68 and 0.5/91 at full
  precision. Measured on the shipped bytes with the shipped checks: oracle
  1.000, with all eighteen positives true and all sixteen negatives silent;
  nop 0.000; a stub built from the artifacts list alone -0.029, earning
  all_artifacts_exist and firing negative_program_ignores_its_input; and a
  delivery with one cent wrong in one row of deferred_containers.tsv, the
  manifest honestly digesting that row, 0.912, losing the vessel family and the
  manifest and nothing else. No check raised out of its body in any of the four
  runs. These four were measured by running each registered check against a
  prepared workspace; the harbor run --env docker ladder, five oracle runs plus
  nop plus stub, has still to be run against this revision of the bundle.
caveats: >-
  EL_NO_CUTOFF, EQ_UNKNOWN_UNIT and EL_NO_OBLIGATION are unreached on the
  shipped shift and reached on all three minted shifts, so the program tier
  grades all three branches. corpus_sentinel_note.txt is written from what the
  shift it sits in actually contains, so the note stays true on every shift the
  corpus mints, and an agent that implements the branches it names as unreached
  is graded on all three by the unseen shifts.
```
