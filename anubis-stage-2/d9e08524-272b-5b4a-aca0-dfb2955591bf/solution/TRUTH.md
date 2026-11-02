# TRUTH.md - d9e08524-272b-5b4a-aca0-dfb2955591bf

## Defect

The agent is handed a package registry's complete written index format and policies plus a set of
binary index shards, and none of it can be consumed at face value. Eleven optional wire transforms
are announced bit by bit in each shard header, six registry constants those transforms and the
resolution rules depend on are withheld, and the only route to them is eliminating published
candidates against a calibration slice. The rules sit in five policy documents in alphabetical,
not application, order, one licence rule runs against the instinct every package maintainer
carries, and the lock plan of each workspace is the solution of a coupled search rather than a
lookup. The agent must build a reusable planner that repairs all of this. The defects are these.

1. (focal) A plain shard reader walks off the end of every field shard, because the stored block
   count carries a salted bias modulo a withheld limit and the status word that holds the dependency
   entry count is rotated by a withheld base. Defeats `trap_biased_count` and
   `trap_rot_status`.
2. (focal) Artifact bytes are masked with a CRC-32 keystream of the withheld salt, the shard nonce,
   the block key and the record ordinal, and under DRIFT_KEY the block key depends on the true bytes
   of every logically earlier block, which are shuffled by a withheld multiplier. Defeats
   `trap_mask_bytes`, `trap_drift_key` and `trap_block_permute`.
3. (focal) Version codes and publish days are stored as first and second order differences, and
   repeated dependency entries arrive as one byte tags into a ring whose span is withheld. Defeats
   `trap_chain_version`, `trap_delta2_day` and `trap_backref_deps`.
4. (focal) Lock plans are a search: every valid plan must lock exactly the packages that the
   workspace and the active entries of locked versions require, entries are active only when the
   least feature fixpoint enables their gate, and the workspace receives the valid plan with least
   footprint under two tie breaks. Defeats `shipped_workspaces_are_settled` and all
   sixteen held out checks.
5. (drift) The licence that governs a renamed package is the one recorded against the earliest name
   of its chain. Taking the newest record forbids packages a workspace may lock, admits packages it
   may not, and leaves the latency workspace with no valid plan. Defeats
   `shipped_workspaces_are_settled`, `held_out_invert_chain` and
   `held_out_flip_licence`.
6. (drift) A single pass over dependency entries under activates features in any workspace whose
   activation chain is longer than one link. Defeats `held_out_feature_cycle` and the shipped
   plan check.
7. (trap) The shard nonce and every record count are big endian under ENDIAN_ISLAND, and the block
   trailer covers the bytes either way. Defeats `trap_endian_island`.
8. (trap) Every block key is combined with the nonce of the companion shard of the same tier, so no
   shard can be attributed to a package in isolation. Defeats `trap_xref_key`.
9. (trap) Every block trailer is followed by pad bytes that no trailer covers. Defeats
   `trap_split_tail`.
10. (trap) A version published exactly the quarantine days before the snapshot is eligible; a strict
    comparison moves a lock plan on every corpus. Defeats `held_out_temporal_edge` and the
    shipped plan check.

The reference is Python 3.12 with the standard library only. Grading runs on two channels:
`tests/test_output.py` carries the deterministic rewardkit criteria over the delivered program and
documents, and `tests/judge.toml` carries the judged criteria over the trajectory and the delivered
program. `tests/reward.toml` gives each channel half of the final reward. The two are disjoint.

Out of bounds: pasting shipped answer figures into the program is caught by
`negative_hardcoded_sample_answers` and by the generalisation tier, whose corpora each
carry their own constants; keying behaviour off shard file names is caught by
`negative_filename_dependent_behaviour`; consulting the example report while deriving
is caught by `negative_reads_supplied_answer_data_at_runtime`; output that varies
between identical runs is caught by `negative_nondeterministic_output`.

## Load-bearing work

The graded artifacts are `/app/out/optimize.py`, `/app/out/scenario_visible.json`,
`/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json`,
`/app/out/scenario_latency.json`, `/app/out/perf_report.json`,
`/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json` and
`/app/out/data_quality.json`.

- `optimize.py` takes an input directory and an output directory and must plan any population drawn
  from the policies, not only the shipped one.
- Each `scenario_*.json` carries the workspace, snapshot day, copyleft setting, footprint, package
  count, quarantined record count and every locked package with version, enabled feature mask,
  governing licence family and bytes.
- `perf_report.json` carries the field decode counts, decoded, excluded and locked bytes, the byte
  residual, the footprint of every workspace and the six recovered constants.
- `bottleneck_analysis.json` carries, per workspace, the held back packages and the permissive and
  copyleft partition of the locked packages.
- `data_quality.json` carries the index integrity counts and the excluded bytes by cause.
- `recommendations.json` is the derivation record: sixty candidate verdicts with falsifiers,
  falsifier totals, the calibration comparison table, settlement passes per workspace and the
  licence divergence list.

Out of bounds by design: the documents never state the order in which constants can be eliminated,
the order in which rules apply, a procedure for the plan search, or how many packages any plan
locks.

## Verification

`tests/test.sh` clears any stale reward file, locks `/logs/verifier` to root, restricts `/tests`
and hands over to pinned `harbor-rewardkit==0.2.1` with `exec`. rewardkit scores each
criterion-bearing file at the top of `tests/` and writes `reward.json` and `reward-details.json`
itself; test.sh writes no reward bytes, so a grading crash leaves a verifier error rather than a
score. `tests/reward.toml` turns the two channel sums into the one `reward`, each channel counting
for half: `test_output = 0.5 / 139` and `judge = 0.5 / 19`. Best is 1, doing nothing is 0, worst is
minus 1, and no clamp is applied anywhere.

Channel A is `tests/test_output.py`: 35 rewardkit criteria, 31 positive with a positive weight total
of 139 and 4 negative with a negative weight total of minus 18. Every check takes the workspace and
returns a bool, so bad or missing agent output makes a check return False instead of aborting the
run.

The weight sits on the tiers whose corpora carry their own withheld constants, because those are the
tiers a memorised answer cannot satisfy. Shipped tier at weight 1: `delivers_every_document`,
`shipped_index_is_decoded`, `shipped_workspaces_are_settled`, `shipped_derivation_is_recorded`.
These four read the documents already in `/app/out`, which a program that replays memorised answers
can satisfy, so they are priced as the existence checks they are. Trap tier at weight 5:
`trap_mask_bytes`, `trap_chain_version`, `trap_delta2_day`, `trap_drift_key`, `trap_block_permute`,
`trap_backref_deps`, `trap_endian_island`, `trap_biased_count`, `trap_rot_status`, `trap_xref_key`,
`trap_split_tail`. Generalisation tier at weight 5: `held_out_tie_footprint`,
`held_out_temporal_edge`, `held_out_invert_chain`, `held_out_flip_licence`,
`held_out_empty_copyleft`, `held_out_feature_cycle`, `held_out_add_entity`, `held_out_yank_wave`,
`held_out_scale_bytes`, `held_out_unregistered_burst`, `held_out_allow_copyleft`,
`held_out_narrow_roots`, `held_out_wide_catalogue`, `held_out_no_backref`, `held_out_extend_chain`,
`held_out_early_snapshot`.

Two comparison families, so one wrong figure costs one family rather than the whole channel. The
trap tier compares the figures that follow from decoding alone: the whole integrity report, the
recovered constants, and the shard, block, record, dependency entry, decoded byte and excluded byte
counts. The generalisation tier compares the figures that follow from settling: the five lock plans,
the bottleneck analysis, the locked bytes, byte residual, workspaces resolved and footprint by
workspace, and the whole derivation record.

Negative checks: `negative_hardcoded_sample_answers` at minus 5,
`negative_filename_dependent_behaviour` at minus 5,
`negative_reads_supplied_answer_data_at_runtime` at minus 5, `negative_nondeterministic_output` at
minus 3. Each returns True only when its shortcut is present, and the filename and example report
detectors stand down on an unstable program, so one decision never fires two of them.

Channel B is `tests/judge.toml`, nine criteria with a positive total of 19 and a negative total of
minus 8. R1 to R5 are constraint criteria at weight 3, one per working rule the instruction states,
each quoting its sentence; R6 is a negative constraint at minus 3 for writing under `/app/data`. R7
is a negative conduct criterion at minus 5 for claiming control agreement the delivered record
contradicts. R8 judges the quality of the delivered program at weight 3 and R9 the rehearsal
confirmation at weight 1. Every criterion reads the trajectory or the delivered program, because
every figure the agent derives lands in a document channel A already asserts exactly, so a judged
criterion over any of those figures would pay a second time for one fact.

Observable partition. Channel A asserts the delivered documents: artifact presence and serialised
form, every field of the five lock plans, the performance report, the bottleneck analysis, the
integrity report, the recovered constants and the whole derivation record including the falsifier
label of every rival, the falsifier totals, the published and reproduced control figures, the
settlement passes and the licence divergence list. Channel B asserts nothing about those
documents. It asserts the timing of the verdict statements, the control comparison written before
the field shards, the licence family listing written before settling, the clean regeneration, the
renamed copy run, the untouched input, the honesty of the agreement claim, the readability of the
program and the rehearsal confirmation. No observable appears on both sides.

## Root cause

**Constants are published only as a candidate space.** Six values are withheld, each one of ten
published candidates, and six control figures over a held out calibration population separate them.
Nothing downstream can start until the elimination finishes.

**The transforms are sequential.** Chained version codes, second order days, the drifting key and
the dependency ring each need earlier records or blocks decoded first, the shuffle must be inverted
before the drift can be rebuilt, and the companion key needs another shard decoded first.

**Identity and licence are derived.** Rename chains merge versions published under several names
into one package reported under its newest name, while the governing licence belongs to the
earliest name.

**Lock plans are a coupled search.** Feature fixpoint, active entries, ranges, licence settings and
eligibility interact, so no forward pass or greedy choice reaches the least footprint plan; the
search must backtrack.

**Red lines.** Every graded answer is reachable from `instruction.md` and `environment/data/` alone.
No graded value depends on a seed or a tests only file. Rehearsal shards carry a flag word of zero
and leak no keyed constant. No `cheat/` folder exists. The declared artifact list is frozen.

## Solution shape

1. Parse the calibration slice: candidate lists, snapshot day and the six control figures.
2. Walk the calibration shards for every salt, bias limit and rotation base, keeping combinations
   whose trailers and block areas close.
3. Decode each survivor under every span and multiplier and compare CTRL-1 to CTRL-5.
4. Fix the quarantine days with CTRL-6 and require exactly one surviving assignment.
5. Weigh every rival with the other constants at their recovered values and record its falsifier.
6. Decode the field shards with companion keys and tally the integrity counts.
7. Merge rename chains and assign governing families from the earliest names.
8. Filter eligible versions per workspace by yank, snapshot and inclusive quarantine.
9. Search each workspace depth first over the lowest named open package with branch and bound on
   footprint, recomputing the least feature fixpoint at every node.
10. Break footprint ties by the larger version code sum, then by the plan text.
11. Count settlement passes on each plan and settle again under the newest name reading.
12. Report held back packages, family partitions and the byte conservation identity.
13. Write the nine documents with two space indentation and sorted keys.

## Ordered plan

1. Read `instruction.md` and every document under the input directory; the five working rules
   stated there are what R1 to R5 grade.
2. Confirm a plain reader on the rehearsal shards. Earns R9.
3. Eliminate the constants, stating each rival's falsifier as it is set aside. Earns R1.
4. Write out the reproduced against published comparison before touching field shards. Earns R2 and
   avoids R7.
5. Write out the governing licence family of every multi name chain before planning. Earns R3.
6. Settle every workspace with the feature fixpoint inside the search, taking the governing licence
   from the earliest name of each chain.
7. Build the divergence list under the newest name reading.
8. Clear the JSON documents, keep the program and regenerate everything in one clean run. Earns R4.
9. Run the program over a renamed copy of the input and compare. Earns R5; leaving the input alone
   avoids R6.

## Pitfalls

- Trusting the stored block count fails `trap_biased_count`.
- Reading the status word unrotated fails `trap_rot_status`.
- Advancing by header, records and trailer only fails `trap_split_tail`.
- Reading the nonce little endian under the island fails `trap_endian_island`.
- Decoding a shard in isolation fails `trap_xref_key`.
- Treating blocks in file order fails `trap_block_permute`.
- Keying the mask with the block nonce alone fails `trap_drift_key`.
- Reading version codes or days as absolute values fails `trap_chain_version` and
  `trap_delta2_day`.
- Ignoring ring tags fails `trap_backref_deps`.
- Taking the licence from the newest name fails every shipped plan check and every held out check.
- One feature pass fails `held_out_feature_cycle` and the shipped plan check.
- A strict quarantine comparison fails the shipped plan check and every held out check.
- Preferring the newest versions fails every plan check.
- Reversing the tie break fails `held_out_tie_footprint`.
- Hardcoding the recovered constants fails the whole trap and generalisation tiers.

## Provenance

```yaml
uuid: d9e08524-272b-5b4a-aca0-dfb2955591bf
instance_id: d9e08524-272b-5b4a-aca0-dfb2955591bf
task_name: terminal-bench/d9e08524-272b-5b4a-aca0-dfb2955591bf
fix_patch_sha256: 2e629a0759123b82a80bce9a2c145040fbc4fdd3531ab964e4961c8f9c854ae7
solve_py_sha256: 681c2ca6bd42089b574c18d62a0c223f7ede6d036dbde6ded62b383eb8971b11
language: python
status: complete
harbor_oracle_test_channel: 1.000  # five harbor trials, each exactly 1.000, test channel only
harbor_nop_test_channel: 0.000  # one harbor trial, test channel only
harbor_stub_test_channel: 0.000  # declared artifacts created empty, test channel only, no check paid
```

The three figures above are TESTS-ONLY. They come from runs on a copy whose `tests/judge.toml` was
removed and whose `tests/reward.toml` was set to the test channel alone at `1 / 139`, because the
oracle, nop and stub agents make no model calls and leave no trajectory for the judged channel to
read. No judged-channel oracle score exists or can exist.
