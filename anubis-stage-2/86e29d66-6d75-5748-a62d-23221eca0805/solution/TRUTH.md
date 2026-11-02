# TRUTH.md - 86e29d66-6d75-5748-a62d-23221eca0805

## Defect

A distributed training run was restarted twice and its bookkeeping never recovered. The archive under the input mount holds the micro step log of the run split across twenty three segments, the shard plan split across ten table files, the schedule definition, the accumulation policy, the restart exceptions, the probe log, the checkpoint index and six notes that state every rule.

(focal) The optimizer step ledger has to be rebuilt from the micro step log, and the log cannot be read in file order or in line order. Three segments hold the lowest sequences in the run, every segment stores its lines in reverse, and the only authority on order is the `sequence` field. A reader that trusts arrival order produces a ledger whose windows close at the wrong records, which then poisons the schedule, the probe match, the selection and every roll up.

(focal) Window width is not a constant. It resolves through four layers, profile override over restart exception over phase over policy default, and the clamp applies once after the layer is chosen. Width changes mid window, so a window that is already half open can close on the very next record when the active width shrinks. The five lanes differ only in their overlay, so the same stream yields five different ledgers, and the deltas between them are graded.

(drift) The `latency` lane looks like a schedule fault. Its curve is short, its probe match collapses to two, and its averaged metric moves. The evidence points at the schedule layer. The cause sits in the assignment layer: the lane bars one worker, every record owned by that worker is refused as `owner_excluded`, and the shorter ledger is a downstream consequence. Chasing the curve produces a plausible and wrong rewrite of the rate function.

(trap) The shard move table holds one row that takes effect inside the run and two rows that take effect past the last sequence. The run itself is honest: records before the live move carry the old owner and records after it carry the new one. An implementation that resolves ownership from the shard plan alone manufactures a block of `owner_mismatch` refusals that do not exist. The tempting repair is to stop validating ownership. That repair is invisible on the shipped archive, where no genuine mismatch exists, and it collapses on the unseen archives, where a stale owner record, a worker absent from the roster and a barred worker all have to be separated.

## Load-bearing work

Thirteen stages run in series and two of them converge on state derived twice over.

1. Role discovery. File names carry no authority. A JSON document announces itself through its `document` key, a table announces itself through its header signature, and a log line announces itself through its `record` key.
2. Stream ordering. Every log line from every segment forms one stream ordered by ascending `sequence`. Two lines that share a sequence are settled by keeping the one whose canonical serialization sorts first, and a dropped micro line counts as `duplicate_sequence`.
3. Shard facts. Plan rows are walked in `order_key` order. The first row for a shard fixes its owner, its example count and its status, and a later row that disagrees raises `manifest_conflict`. Effective size subtracts the held out rows and the duplicate rows marked for removal.
4. Ownership timeline. The owner of a shard at a sequence is the plan owner replaced by the last applicable move row, with the last sorting target owner settling a tie.
5. Phase timeline. Phase openings in the stream decide which phase rules at a sequence.
6. Refusal. Ten reasons resolve in a fixed order and the first match wins, so a retired shard beats an owner fault and an owner fault beats an out of range example count.
7. Overflow. A record that survives the ten reasons but carries the overflow flag is skipped rather than refused, and it is counted in its own bucket.
8. Rollback. Each restart withdraws the accepted records that sit strictly between the write point of its resume checkpoint and its own sequence. Withdrawn records leave the accepted stream and land in their own bucket.
9. Cursor reconciliation. The recorded cursor of every checkpoint is compared against the accepted count rebuilt at that write point. This is the first convergence: the ledger reconstructed from the log has to agree with the ledger the run recorded, and the disagreement count is graded.
10. Accumulation. The walk carries pending state across restart boundaries. When a restart is crossed, a non empty pending window is discarded unless the carry decision resolves true through its own three layers.
11. Schedule. Each closed step gets a rate in milli units from warmup, sawtooth decay and three ordered percentage scales. Rounding is half to even at every division and the order of the scales changes the result.
12. Cadence and selection. Logged steps, expected probe steps, matched probes, stray probes and absent probes all follow from the final step index. Selection takes the lowest metric, then the lowest step, then the lowest probe name, and resolves the chosen checkpoint through its supersession chain.
13. Roll ups. Coverage is the second convergence: planned examples derived from the shard plan has to be reconciled against accepted examples derived from the stream, and the signed gap is reported.

## Verification

The reference run writes ten deliverables and scores the full deterministic weight of 87. Twenty nine checks run. Five are cheap presence and shape checks. Ten grade the shipped archive against frozen expectations covering the ledger, the curve, the probe outcome, the split window attribution, the barred worker lane, the nine fingerprints, the signed deltas, the stage ranking, the recommendation codes and the two identities. Ten grade four run archives that no shipped file can influence: one dense archive with every refusal reason live, one with vanishing schedule spans, one too short to close a single window, and one with scattered sequences and a clashing plan row. Four negative checks price the obvious forgeries: negative_hardcoded_sample_answers, negative_filename_dependent_behaviour, negative_nondeterministic_output and negative_rebinds_verifier_dependencies.

The carry behaviour of the short window lane and the widened decay span of the steady lane are graded by the lane ledger and lane curve checks that cover all five lanes, rather than by separate per lane checks.

## Root cause

The mechanism is a running accumulation window that survives a restart, combined with a width that is resolved per record rather than per run. The rule that breaks naive work is the partial window rule: when a restart is crossed with a non empty pending window, the pending records are discarded unless carry resolves true.

On the shipped archive the restarts sit at sequences where the accepted count is an exact multiple of four. The default width is four, so at the reference lane the pending window is empty at both boundaries and the discard path never runs. Every visible window is therefore intact, and a reader who counts accepted records and divides by the width gets the right answer for the reference lane. The same division is wrong the moment the width is six or three, because the boundary now falls inside a window, and it is wrong on the unseen archives, where the boundaries are placed without regard to the width.

The second half of the mechanism is that the cursor recorded by a checkpoint is a fact about the run, while the accepted count is a fact about the reconstruction. They agree on the reference lane and disagree on the lane that bars a worker. An implementation that trusts the recorded cursor instead of rebuilding it reports zero drift everywhere and loses the graded drift figure.

## Solution shape

One program, pointed at a data directory and an output directory, with no state outside those two places. Discovery is content addressed. The stream is ordered once and reused by every lane. Shard facts, ownership timeline and phase timeline are computed once. Each lane then runs the refusal pass, the rollback pass, the cursor pass and the accumulation walk over its own view, because the barred worker list changes which records are accepted and therefore changes every later number. Arithmetic is integer only with a single rounding helper, and the rounding helper owns the zero denominator rule so that the event count is accurate. Serialization is canonical with sorted keys, tight separators and one trailing newline, and every report seals itself with a fingerprint computed over its own finished body with the fingerprint key removed.

## Ordered plan

1. Read the six notes and the output contract before touching the data.
2. Build the role map from content signatures.
3. Order the stream and settle shared sequences.
4. Build shard facts, effective sizes and the planned total.
5. Build the ownership timeline and the phase timeline.
6. For each lane, refuse, skip, roll back and reconcile cursors.
7. Walk accumulation with carried pending state and restart handling.
8. Price each closed step through warmup, decay and the three ordered scales.
9. Match probes, select the best checkpoint through supersession, stop on strikes, average the eligible tail.
10. Emit the five lane reports, then the four roll ups, each sealed and canonical.

## Pitfalls

Reading segments in directory order. Treating the window width as a constant. Dividing accepted records by the width. Discarding a pending window at every restart regardless of the carry layers. Applying the percentage scales in the wrong order or folding them into one division. Using floating point for the rate curve. Trusting the recorded cursor. Letting a barred worker record reach the accumulation walk. Selecting a superseded checkpoint. Writing the fingerprint over a body that already holds the fingerprint key. Emitting trailing whitespace or a second newline.

## Provenance

```yaml
uuid: 86e29d66-6d75-5748-a62d-23221eca0805
instance_id: 86e29d66-6d75-5748-a62d-23221eca0805
task_name: terminal-bench/86e29d66-6d75-5748-a62d-23221eca0805
fix_patch_sha256: fd20fa2ee2d99405cde3d422dc798b4795825415b463bd8da19a5e4ec7ca7552
solve_py_sha256: 535b134c3847fe8f881f8f92365c8c77e26c4d0193d17a16d39f36e1186f78ca
language: python
```
