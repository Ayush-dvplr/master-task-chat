# STRATA extent relocation planner

## Defect

The relocation control plane has no working planner and the plan it owes has
never been produced. The corpus is complete and internally consistent; what is
missing is the program that turns it into twenty-four plan artifacts, plus the
written closing summary that reports the plan back. The agent delivers both, and
the planner itself as `stratactl.py`, so the plan can be reproduced on a corpus
the agent never saw.

Focal items, each of which the supplied corpus actually exercises:

- The eviction fixed point. Shedding runs the full eight rounds and twenty two
  objects leave in the last one, so a planner that stops early or settles the
  rounds in the wrong order lands a different plan.
- The four key primary path ladder. The corpus drives it to every level: 1537
  clusters hold a single path record, and of the rest 214 settle on depth, 54
  on UTF-8 byte length, 41 on code point order and 21 on the ordinal.
- The conservation identity. All forty-two devices close to a zero residual,
  which holds only when extent repair, replay, placement, sharing, scheduling
  and cutover agree with one another.
- Physical against logical space. Holes, preallocated ranges and inline ranges
  each have their own treatment and only data ranges are read from the source.

Drift items, values present in the corpus that the specification marks advisory
and that a planner is expected to notice rather than act on: the per record
status fields that do not settle relocatability on their own, and the hold
notices, which are recorded and reported without excluding an object by
themselves.

Traps, each sprung by the shipped data:

- Superseded rows. Every authoritative table carries revisions, and the last row
  in a file is routinely the wrong one. `object_inventory.jsonl` reports the
  count it discarded per object.
- Unicode normalisation. 2735 path records arrive NFC and 259 NFD, and a pair
  differing only in form is one path. Among the symlinks, 437 targets are
  declared NFC and 43 NFD; every declaration agrees with the final raw target.
- The symlink space boundary. The boundary falls at 59: a target of at most 59
  bytes is fast and occupies nothing, one longer occupies a whole allocation
  unit. Targets sit at 57, 58, 59, 60 and 61 bytes, 16, 26, 20, 8 and 17 of them
  respectively, so reading the boundary as 60 moves `physical_bytes` on 8 of the
  480 symlinks and reading it as 58 moves it on 20.
- The barrier boundary. 431 events are absorbed, every one of them for sitting
  at or before its pool barrier, and the corpus carries events exactly on the
  boundary and one past it.
- Malformed extents. Generations, overlaps and ranges reaching past the end of
  their object all appear, each with a stated repair and a stated composition
  order rather than a rejection, and 691 extents arrive with a length of zero,
  which makes each of them void.
- Shared paths and exact ties. Two inodes hold one canonical path, which the
  path index gives to the lower; two relocatable objects whose only path is
  such a shared path compete for one overcommitted device and one shared
  physical range; and activity events share a sequence and ordinal, one pair
  differing in kind and one in inode. The path index's lowest-inode rule, the
  final inode keys of ownership, shedding, the delta work set and cutover, and
  the kind and inode keys of the replay order therefore all decide graded bytes.
- Device number overflow. 74 of the 280 special nodes carry a minor that the
  formula cannot hold, and the overflow has its own repair and is reported.

## Load-bearing work

1. Physical and logical space are distinct. Holes, preallocated ranges and
   inline ranges are never copied as data; only data ranges contribute copy
   work.
2. Placement is a fixed point. The attribution is rebuilt from scratch at the
   start of every round, and within a round the claims move as the walk
   proceeds: the moment a device sheds, the attributed bytes of the object it
   shed leave its claim and arrive in the claim of the spill device, so a device
   is judged against the claim it holds when the ascending walk reaches it.
3. A hard-link cluster's primary path is chosen by the complete four-key chain:
   path depth, UTF-8 byte length, canonical path and arrival ordinal.
4. Authoritative rows are selected by each table's revision rule, never by
   whichever row happens to appear last in a file.
5. Extent repairs are applied in order: overlap truncation, clipping to the
   object's logical size, then the void outcome.
6. Relocation eligibility evaluates all four documented conditions in order and
   records the first reason that excludes an object.
7. Durable checkpoint work is invalidated when later activity intersects it;
   merely touching an endpoint does not invalidate it.
8. Empty groups still emit rows. This includes unused windows, devices with no
   placement, and relocatable objects with no extended attributes.

## Verification

The test channel is `tests/test_output.py`, 35 rewardkit criteria: 27 positive
summing to 81 and 8 negative summing to 34 in absolute terms. Two positives
cover delivery and framing, `declared_artifacts_present` and
`declared_artifacts_parse`, each weight 1. Twenty-three compare one artifact
whole against the reference, ten of them at weight 1 and thirteen at weight 5;
`artifact_cli_contract` is weight 1 and `exit_codes` is weight 3. Every artifact
comparison checks the delivered bytes on the shipped corpus and planner output
on nine exact corpus shapes: shipped-seed regeneration, two unseen seeds, an
alternate directory, opaque names, misleading names and extensions, an isolated
edge corpus, reserve perturbation and reversed rows. A sample-only, filename-
dependent or order-dependent plan therefore fails the same whole-artifact check
as any other wrong plan.

The eight negatives are `negative_hardcoded_sample_answers`,
`negative_corpus_directory_dependence`,
`negative_hardcodes_machine_path`, `negative_ignores_perturbed_input`
and `negative_writes_undeclared_files` at weight -5, and
`negative_nondeterministic_output`, `negative_input_order_dependent_output` and
`negative_nonstdlib_imports` at weight -3. Each asserts its own failure mode,
and three sit behind `repeats_itself`, `directory_stable` or `tracks_corpus`, so
one bad decision fires one penalty rather than several. The cleanliness check
inspects both the uploaded `/app/out` directory and the hidden rerun, including
dotfiles, directories, symlinks and special files, but remains one criterion.

The judged channel is `tests/judge.toml`, 20 criteria: 15 positive summing to 39
and 5 negative summing to 19 in absolute terms. Four positives cover instruction
following, ten cover independently evidenced verification conduct, and one
covers source maintainability. The negatives cover corpus mutation, contradicted
reporting, contradicted execution or input claims, unchanged failing retries and
final artifact hand edits. Exact artifact values are owned only by the
deterministic channel. `tests/reward.toml` gives each channel half the reward, at
`0.5 / 81` and `0.5 / 39`.

The oracle `solve.py` and the reference embedded in `tests/test_output.py` are
separate implementations of the specification. Compared byte for byte on the
shipped corpus and all nine generated shapes, each produced all 24 plan
artifacts with zero differences. Graded by the shipped `tests/test.sh` in the
Linux verifier image, at rewardkit's default concurrency, the oracle's delivered
output, which `solve.sh` leaves owner-only, returned true for all 27 positive
checks and false for all 8 negatives. These are deterministic-channel results;
no judged-channel execution score is claimed.

## Root cause

The task is hard because the plan is one connected object: twenty-four artifacts
that each depend on the ones above them, closed by a conservation identity and
two digests that agree only when the whole plan agrees. The corpus arrives flat
in fourteen encodings across 51 shards, and its basenames and extensions are
nonbinding, so the first work is content decoding and complete-schema
identification. After that every stage feeds the next, and a single rule read
loosely, such as eviction order, cycle tracking, checkpoint absence or split
rounding, propagates through later artifacts and breaks exact closure.

## Solution shape

`solve.py` reads the corpus once into seventeen logical tables, resolves the
authoritative revision of every record, and then derives the artifacts in
dependency order, holding one in-memory plan rather than recomputing shared
intermediates per artifact. It decides each file's encoding from the file's
content alone, across all fourteen encodings, and accepts a table only when the
decoded records carry exactly one schema's complete field set; filenames and
extensions decide nothing. Keyed formats reconstruct their implicit first field.
`solve.sh` installs `solve.py` as `/app/out/stratactl.py` and runs that delivered
file for every fixture check, for the final generation and for two repeat runs
whose output it compares byte for byte with the delivered artifacts.

Checkpoint absence is normalized only from the documented `NIL` token; numeric
zero remains numeric. Symlink cycle tracking starts from an empty reached-target
set, leaving the starting path unseeded and enforcing repeat detection before
the eight-hop cap. Symlink arrival forms describe the final raw targets. Split
scheduling takes a fitting residual whole and rounds available room only when
the residual does not fit.

Placement is the only stage that iterates. The attribution of physical copies to
share domains is rebuilt from the current placement at the start of each round;
the devices are then walked in ascending identifier and each sheds one object to
its spill device if its claim has it overcommitted at the moment the walk
reaches it, with the shed bytes moving out of one claim and into the other
immediately, so a device pushed over by what a lower numbered device handed it
sheds in the same round. Rounds stop when one sheds nothing or when the eighth
completes. The victim within a device is chosen by weakest class, then largest
attributed bytes, then primary path in code point order, then smallest inode,
among objects never shed before.

Everything after placement is a single pass: the delta and metadata work sets,
the window packing under the byte and descriptor budgets, the split and
descriptor ledgers, the cutover order and its rollback, and finally the
conservation closure, the manifest digest and the summary.

## Ordered plan

```
tier 1  object_inventory.jsonl        corpus only
        device_topology.json          corpus only
tier 2  extent_map.tsv                inventory
        symlink_topology.jsonl        inventory, paths
        mutation_replay.jsonl         inventory, paths
tier 3  scope_resolution.csv          inventory, replay
        link_clusters.jsonl           replay, scope
        resume_state.jsonl            extents, replay, scope
        xattr_ledger.csv              inventory, scope, replay
        special_nodes.tsv             inventory, scope
tier 4  placement.csv                 topology, extents, scope, clusters
        sharing_expansion.jsonl       extents, placement, scope, clusters
        allocation_projection.csv     topology, placement, sharing
        delta_workset.tsv             resume, placement, sharing, clusters
        metadata_workset.jsonl        clusters, xattrs, nodes, symlinks
        window_schedule.tsv           work set, placement, topology
        split_ledger.jsonl            schedule, work set
        descriptor_budget.csv         schedule, topology
tier 5  cutover_sequence.txt          clusters, split ledger, scope, placement
        rollback_plan.jsonl           cutover, resume, split ledger, clusters
        conservation.json             all preceding tiers
        cli_contract.json             planner contract
        manifest.json                 the preceding artifacts
        summary.json                  manifest and table counts
```

Step by step:

1. Load the seventeen logical tables by matching record schemas rather than
   relying on file names. Decode all fourteen supported formats.
2. Select authoritative barriers, capacities, geometry, objects, extents,
   attributes, special-node records and routes using their documented ranking
   rules.
3. Build the object inventory and target topology, performing unit conversion,
   mode normalization and reserve calculation at the specified stages.
4. Repair and classify extents. Round physical allocation using the pool unit,
   not the target device's scheduling unit.
5. Canonicalize paths using NFC and classify symlinks without following their
   contents. Enforce the hop cap and distinguish cycles, capped chains,
   dangling targets, outside targets and inside targets.
6. Replay activity in `(seq, ordinal, kind, ino)` order against each pool's
   barrier. Apply path and attribute mutations only after the ordered outcome
   checks succeed.
7. Resolve relocation scope and hard-link clusters, then determine checkpoint
   outcomes, migrated attributes and special-node recreation operations.
8. Place objects on target devices and run shedding for at most eight rounds,
   rebuilding the sharing attribution at the start of each round and moving each
   shed object's bytes between the two claims as the ascending walk reaches each
   device.
9. Build the delta and metadata work sets. Pack copy work into windows under
   both byte and descriptor limits, producing the split and descriptor ledgers.
10. Exclude objects with deferred bytes from cutover, order remaining paths by
    depth, path and inode, construct rollback operations, close conservation,
    and emit the manifest and summary.

## Pitfalls

- Taking the last row in a file as authoritative. Every table carries revisions
  and the ranking rule decides, not file order.
- Freezing each device's claim for the whole shedding round. The attribution is
  rebuilt between rounds, but inside a round the claims move as devices shed,
  and treating them as fixed changes ten of the twenty-four artifacts while
  leaving every aggregate and the conservation residual intact, so the identity
  still closes on a wrong plan.
- Stopping the primary path ladder after the second key and settling what is
  left by arrival order. It renames the primary on 23 clusters, and every
  artifact ordered by path follows it there. Stopping after the third key keeps
  every primary but cannot report level 4 on the 21 clusters that need it.
- Comparing the barrier with the wrong strictness, or treating a committed range
  as invalidated by an activity that merely touches its endpoint.
- Rounding physical allocation with the device scheduling unit rather than the
  pool unit.
- Dropping rows that came out empty. Unused windows, devices that received
  nothing and objects with no extended attributes all still produce their row.
- Computing the closure digests over a sorted or incidental order rather than the
  order the specification names.
- Sorting JSON object keys. The key order is the order the specification lists.

## Provenance

```
bundle                       82423338-4b5a-588b-b916-a9b76575b181
corpus files                 52 (SPEC-STRATA.md plus 51 shards, 14 encodings)
sha256-16 solve.py           e1d6264d31384632
sha256-16 solve.sh           6a454d02d24c50bb
sha256-16 test_output.py     378f32db5ef70b5a
sha256-16 SPEC-STRATA.md     6477be23ddaa9565
manifest_digest              04a13a3c506e2f68
relocatable objects          1867
excluded objects             739
hard link clusters           1867
copy items                   2162
metadata operations          9609
cutover steps                1697
```

Closing figures for the supplied corpus, as the written summary reports them:

```
sum of descriptor utilisation ppm                         430682243
window placements opening a descriptor                          1110
total scheduled bytes                                      386514944
total delta copy bytes                                     492699648
total metadata-operation bytes                              97804288
total attributed bytes                                     621969408
sum of device headroom                                     956956684
inode on schedule data row 500                                100807
bytes placed in window index zero                           22306816
bytes added by cross-domain sharing                        122720256
total deferred bytes                                       106184704
UTF-8 byte length of all cutover paths                          43723
rollback rows with step zero                                      170
reflink metadata operations                                        63
objects shed in the last round                                    22
devices ending overcommitted                                      22
shared ranges producing at least three copies                     56
bytes resumed from durable checkpoints                       49074176
clusters settled at the fourth primary-path key                   21
first cutover path                              /archive/blob-01080
```

Shape and encoding rules the artifacts obey: JSON key order and every specified
row ordering as stated, UTF-8 without a byte-order mark, LF endings, exactly one
final newline, absent text and numeric fields present carrying the specified
empty value, one physical copy per share domain with one owner per copy, and
exit `0` on success, `2` for an invalid argument count and `3` when the corpus
path does not resolve to a directory.
