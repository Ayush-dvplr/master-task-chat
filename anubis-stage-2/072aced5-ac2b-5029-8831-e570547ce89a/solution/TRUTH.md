# TRUTH.md - 072aced5-ac2b-5029-8831-e570547ce89a

## Defect

The keyframe interval ledger holds one record, sequence 20, that records the `interval_basis` value of
thumb-strip in the `decode_order_index` reference domain with a deferred lineage anchor. (focal)
The compile pass that produced the generated interval snapshot has no active anchor to key the
conversion on, so it emits the recorded alternate key as if it were a published
value. (focal) The published value the contract requires is 1883 and the
value now carried through every derived layer is 1359.

Two further records, caption-second and overlay-logo, sit behind an interval index manifest entry pinned
to source generation 42 while the index header claims generation 43. (drift) The
encoder runtime state therefore serves pre amendment values for those two records, which is the
only symptom an operator sees. The interval reconciliation report compares the generated interval snapshot, the interval index manifest and the encoder runtime state
and never reads the keyframe interval ledger, and it skips exactly the two records whose source
generation disagrees, so it publishes an agreement verdict over the remaining
nine. (trap)

The encode operations journal still holds eight pending operations at generation 44: two lineage
supersessions, one retiring ln-12-2 for thumb-strip and one retiring ln-01-2 for alpha-matte, four
amendments covering caption-main, main-program and a competing pair on credits-roll, and two
position addressed rollbacks at target positions 11 and 10. Until the thumb-strip supersession is
replayed the registered active anchor for thumb-strip is ln-12-2, and the generation map row
selected by that anchor yields 1387. (trap) The shipped pre incident snapshot was captured
before sequence 23, so it includes the converted sequence 22 record for audio-bed and
predates the second accepted amendment of chapter-marks.

## Load-bearing work

The solver has to establish that the keyframe interval ledger is the sole authority, that the
reconciliation surface is blind to it, and that the surface verdict therefore
carries no information about correctness. It has to notice that one authority
record carries a reference domain the compile pass could not convert, and it has
to decide which of two generation map rows sharing the alternate key 1359
applies. That decision is settled by the lineage registry, and the registry only
moves when the pending supersession in the encode operations journal is replayed. Before that replay
the honest reading of the shipped evidence selects 1387; after it the honest
reading selects 1883. It also has to apply the rollback rule stated in the policy: a
`target_position` is a one based index into the surviving authority records ordered by ascending
sequence number and recomputed against the state each preceding operation leaves behind, so
position 11 addresses main-program at sequence 29 and, once that withdrawal has settled, position
10 addresses caption-main at sequence 27.

The solver then has to run the recovery in the supported order: correct_interval_record, then regenerate_interval_snapshot, then rebuild_interval_index, then restart_encoder_runtime, then replay_encode_journal, then reconcile_interval_layers. It has
to rebuild the index a second time after the regeneration so that the restored
anchor ln-12-1 is the active one, it has to replay the pending amendments and then the two position
addressed rollbacks, so that credits-roll settles at its generation 44 value 1579 while the
rollbacks withdraw the generation 44 amendments of main-program and caption-main and restore 1796
and 1449, and it has to report chapter-marks and credits-roll as the two render tracks
that keep a later amendment, alongside the retirement of intro-bumper. Those are the only
two render tracks whose durable record is an amendment standing over an earlier amendment
of the same track: caption-main and main-program had their later amendments withdrawn by
the rollbacks, and preview-reel keeps the authority writer row rather than the higher
sequence one. It
has to compute the state digest as the weighted sum modulo 100003 and reach
61038, which appears in no shipped file. `interval_conformance_fixtures.json` confirms
only the conversion machinery, through its reference cohort digest 19135.

## Verification

The test channel is 35 rewardkit criteria in `tests/test_output.py`, each a
top level `@criterion` function of `workspace` returning a bool and registered
once at module level. There are 29 positive checks and 6 negative checks, and
the total positive weight is 109.

Narrative claims ride on one of two work gates rather than on a single value.
`_focal_landed` guards the three checks whose own subject is the corrected
authority record, and asks for generation 44 together with thumb-strip at
1883. Every other recovery claim rides on `_replay_landed`, which asks for
generation 44 together with credits-roll at 1579, a value only the replay
settles and one that appears in no shipped file. A solver that carries out the
recovery and misreads the deferred anchor therefore keeps the ten claims that
do not depend on that anchor and reads 46 of 109, while a hand written forgery
copied out of the shipped derived layers fails both gates and reads 10 of 109,
because credits-roll stands at 1600 in the generated interval snapshot.

`tests/test.sh` clears any stale reward file, locks `/logs/verifier` to root,
restricts `/tests`, and hands over to the pinned `harbor-rewardkit==0.2.1` with
`exec`. It writes no reward bytes itself: rewardkit writes `reward.json` and
`reward-details.json`. `tests/reward.toml` gives each channel half the final
score, dividing the test channel by 109 and the judged channel by 90, so every
positive passing with no negative firing reads exactly 1.0 and doing nothing
reads exactly 0.0.

Every reproducer subprocess runs through `setpriv` as `nobody`, in a session of
its own, with the staged input directory read only and only the staged output
and scratch directories writable, and its process group is killed once the run
returns. `/tests` stays unreadable to `nobody`, so the expectations cannot be
read out of the answer key, and the locked log directory keeps anything the
graded code spawned from writing a score.

Positive checks and weights:

- `summary_contract_keys` at weight 1
- `verdict_layers_compared_order` at weight 1
- `report_root_cause_entity_and_layer` at weight 5
- `summary_canonical_value` at weight 5
- `report_reference_domains` at weight 5
- `generation_after_journal_replay` at weight 3
- `core_active_entity_coverage` at weight 5
- `report_preserves_retired_record` at weight 3
- `resolution_revisited_repair_anchors` at weight 5
- `metrics_weighted_values` at weight 5
- `metrics_state_digest` at weight 5
- `metrics_rank_total_order` at weight 3, which reads the published ranks and
  then runs the reproducer over a corpus whose hdr-grade amendment is shifted by
  one so that its weighted value 2448 equals the alpha-matte weighted value and
  the ascending name tie break alone decides those two ranks
- `resolution_transition_order` at weight 1
- `resolution_dependency_order` at weight 3
- `report_rejected_hypothesis` at weight 5
- `report_minimal_delta` at weight 5
- `core_preserves_later_amendment` at weight 5
- `verdict_authority_anchored_post_replay` at weight 5
- `verdict_zero_post_repair_divergence` at weight 3
- `verdict_pre_repair_divergence_count` at weight 3
- `partition_cover_is_disjoint` at weight 3
- `partition_values_match_core` at weight 1, which compares the partition views
  against the agent's own durable state and so is weighted as the consistency
  check it is rather than as an outcome
- `reproducer_variant_digest_shift` at weight 5
- `reproducer_matches_state_digest` at weight 5
- `artifacts_publish_integers_only` at weight 3
- `composed_equality_under_authority_perturbation` at weight 5
- `composed_equality_under_weighting_perturbation` at weight 5
- `composed_equality_under_reference_map_perturbation` at weight 5

Negative checks and weights:

- `negative_hardcoded_sample_answers` at weight -5
- `negative_filename_dependent_behaviour` at weight -5, which runs the same
  staging twice before it compares a renamed one, so a reproducer that
  disagrees with itself is charged once by
  `negative_nondeterministic_output` rather than twice here
- `negative_reads_training_corpus_at_runtime` at weight -5
- `negative_nondeterministic_output` at weight -3
- `negative_unrelated_records_mutated` at weight -5, which fires only when the
  durable state publishes hdr-grade at its generation 40 declare value 1721,
  the signature of withdrawing an amendment no journal rollback addresses. Any
  other wrong value for that record is an ordinary reasoning error and stays
  charged once, by `core_active_entity_coverage`.
- `negative_previously_valid_state_destroyed` at weight -5

The judged channel is `tests/judge.toml` with 27 binary criteria and a positive
total of 90. R23, R24 and R25 are the negatives. R1 through R14 and R27 are
constraint criteria, each enforcing a sentence stated in `instruction.md`
or in `interval_authority_policy.md`; R16 is the one outcome criterion; R15,
R17 through R22 and R26 judge conduct, and R26 is the one that judges the
quality of the reproducer the agent writes. R27 carries the only stated rule
neither channel could otherwise reach: `/app/out` holds the fourteen named
artifacts and nothing else, which the verifier cannot see because it receives
only the declared artifacts. No criterion reads an observable
any test reads: the tests
read the published artifacts and the executed reproducer, the criteria read the
trajectory and the final message.

## Root cause

One field of one record in the keyframe interval ledger. Sequence 20 records `interval_basis` for
thumb-strip with `reference_domain` set to `decode_order_index` and `lineage_anchor` set to
`pending`. The declared reference domain of the published contract is `presentation_interval_id`.
Everything else in the bundle is a consequence: the generated interval snapshot carried the alternate
key through, the interval index manifest indexed it, the encoder runtime state served it, the interval reconciliation report compared three
layers that all inherited the same value and found them consistent.

A second dispute sits beside it and is deliberately independent of the anchor.
Two writers amend one render track inside a single generation, so neither generation
order nor record order settles which amendment the durable state carries. The
pair on preview-reel at generation 41 is already settled: both rows
predate the compile point, and the generated interval snapshot records the `authority-service` value
even though the `migration-service` row holds the higher sequence number. That
worked precedent is the only statement of the precedence rule anywhere in the
bundle. The live pair on credits-roll at generation 44 is not compiled, so
the precedent has to be recognised and applied during the replay. A solver who
resolves the anchor correctly and takes these two collisions by record order
publishes 59551 rather than 61038 and forfeits the whole composed
equality tier along with R20, the judged criterion that grades the writer
precedence settlement on credits-roll.

## Solution shape

Rewrite sequence 20 into the `presentation_interval_id` reference domain with the published
value 1883, obtained from `decode_order_map.json` by keying on alternate key
1359 and lineage anchor ln-12-1. Regenerate the snapshot, rebuild the
index with ln-12-1 restored as the active anchor, restart the runtime, replay
the eight pending journal operations in ascending `journal_seq` order, resolving each single
generation collision in favour of the authority writer as the settled precedent shows and applying
the two position addressed rollbacks against the surviving set each one addresses, and reconcile
all six layers. Emit the
durable state, the metrics, the resolution, the diagnosis report, the verdict,
the summary, the partition views and a standard library reproducer that publishes
the value, the multiplier, the weighted value and the rank of every render track.

## Ordered plan

1. Read `interval_authority_policy.md`, `generated_interval_snapshot_compiler_notes.md` and `operations_catalogue.json` and establish the authority
   contract and the blindness of the reconciliation surface. Graded by R18.
2. Compare the generated interval snapshot against the keyframe interval ledger and locate sequence 20. Graded by R1, R2 and
   `report_root_cause_entity_and_layer`.
3. Rebuild the index for caption-second and overlay-logo. This is the repair the
   evidence at the start favours and it is revisited later.
4. Replay the pending journal operations. Graded by R17 and
   `generation_after_journal_replay`.
5. Resolve the deferred anchor to ln-12-1 and select the generation map row.
   Graded by R15 and `summary_canonical_value`.
6. Rebuild the index a second time with ln-12-1 restored. Graded by R13 and
   `resolution_revisited_repair_anchors`.
7. Recompute the weighted values, ranks, dependency order and digest. Graded by
   R5, R14 and `metrics_state_digest`.
8. Emit every artifact and the reproducer. Graded by R11, R22,
   `reproducer_matches_state_digest` and
   `reproducer_variant_digest_shift`.

## Pitfalls

- Treating the agreement verdict of the interval reconciliation report as evidence of correctness. Loses
  R24 at minus 5.
- Publishing 1387 for thumb-strip because the index still lists ln-12-2 as
  the active anchor. Loses `summary_canonical_value` at weight 5, the three
  `_focal_landed` checks and the whole value, digest and reproducer tier, and
  reads 46 of 109 once the `_replay_landed` claims are credited.
- Citing the `interval_conformance_fixtures.json` cohort digest as proof that the
  thumb-strip value is settled, when that cohort excludes the deferred entries and
  confirms only the conversion machinery. Loses R25 at minus 5.
- Restoring `pre_incident_interval_snapshot.json`, which was captured before sequence 23
  and therefore carries chapter-marks at 1637 rather than its second amendment 1885.
  Publishing that 1637 is the single observable of
  `negative_previously_valid_state_destroyed`, and it is charged once.
- Rewriting more than one authority record. Loses R19, R10 and
  `report_minimal_delta`.
- Stopping after the index rebuild. credits-roll stays at its generation 41 value 1600
  instead of 1579, thumb-strip and alpha-matte stay on their pre supersession anchors at
  1359 and 1206, and `core_active_entity_coverage` fails. The other two pending
  amendments are withdrawn by the rollbacks, so 1449 and 1796 are already the correct
  durable values for caption-main and main-program.
- Reading the agent evidence directory from inside the reproducer. Triggers
  `negative_reads_training_corpus_at_runtime`.

## Provenance

```yaml
instance_id: 072aced5-ac2b-5029-8831-e570547ce89a
task_name: terminal-bench/072aced5-ac2b-5029-8831-e570547ce89a
solve_py_sha256: e6cffef89217f245703df351db120d844cb2d42c941b39a08608e463eb6b483f
language: python
```
