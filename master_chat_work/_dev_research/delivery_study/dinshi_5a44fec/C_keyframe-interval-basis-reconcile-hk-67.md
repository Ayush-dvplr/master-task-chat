# C card: keyframe-interval-basis-reconcile-hk-67

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/keyframe-interval-basis-reconcile-hk-67`. QC report `Kunwar_Singh_keyframe-interval-basis-reconcile-hk-67_QC_Report.md` (verdict WARN, 0 fails, 3 warns).

## 1 Scores and verdict
- Recorded overall 56.2, tests 26.85, rubric 85.56. QC re-grade: 30 of 109 = 0.2752 vs recorded 29 of 108; "The recorded reward of 56.2 therefore stands as a genuine measurement" (QC :52).
- Verdict **PARTLY** (A file): one wrong value (credits-roll 1600 vs 1579) feeds a value gate `_replay_landed` that also zeroes checks whose own fields may be right. Genuine wrong-value loss 57; gate-only loss 22 (INFERRED per check). Total lost 79/108.

## 2 Inventory
- Domain: video encoding pipeline, keyframe interval ledger reconciliation after a bad replay (authority records, positional rollbacks, state digest). Archetype: **repair/reconcile a stateful journal** + reusable reproducer program run on perturbed inputs.
- Data: 13 files, ~30 KB: interval_authority_policy.md (6.1 KB, 99 lines), compiler_notes.md, keyframe_interval_ledger.jsonl, encode_operations_journal.jsonl, decode_order_map.json (19 rows), track_partition_map.json, pre-incident snapshot (gen 42), interval_conformance_fixtures.json (reference cohort + known pairs), interval_reconciliation_report.json, others.
- Instruction 917 words with an explicit output schema.
- Tests (stacking_check): 35 checks, positive 109, negatives -28 (6). Judge 27 criteria, positive 90, batched. Reward = (tests + rubric)/2.
- Shares (stacking_check): isolated 77.1%, whole_doc 13.8%, shipped_only 9.2%, hidden 0%. G3 13.8% would FAIL our 30% bar; the three composed perturbation checks are the only reruns.

## 3 Test architecture
- Expected values: **hand-frozen literals** `EXPECTED` dict and `INPUT_FILES` embedded as JSON (tests/test_output.py:67-68), e.g. caption-main 1449, credits-roll 1579, main-program 1796.
- Two value gates: `_replay_landed` (298-305; comment 271-279 "Every other recovery claim rides on `_replay_landed` ... the settled 1579 appears in no shipped file") and `_focal_landed` (289, thumb-strip 1883). QC :50: gates concentrate 36/109 and 15/109, accepted as "deliberate anti-forgery coupling".
- Reproducer runs: `_run` stages the reproducer in a temp dir under setpriv nobody (131-229); `_shifted_ledger` / `_perturbed_files` (230-262) perturb authority, weighting, reference map and rank ties; the composed checks compare the reproducer's output on the perturbed set to the expected perturbed result (3x5).
- Partial credit: per-field checks (many and-chains: stacking §2 lists 7 checks with 3-5 chained comparisons) – each check grades one report section.
- Negatives (751-860): hardcoded -5, filename -5, reads training corpus -5, nondeterministic -3, plus two **outcome negatives** unrelated_records_mutated -5 (hdr-grade 1721) and previously_valid_state_destroyed -5 (chapter-marks pre-incident 1637). QC M1 fixed them so an honest blunder cannot fire them (`ROLLBACK_ADDRESSED` must be right first, QC :32).

## 4 Lever table (failed checks)
Root rule: inside a single generation, an `authority-service` record outranks the other record (oracle solution/solve.py:94-96 precedence `(effective_generation, 1 if recorded_by == "authority-service" else 0, seq)`).

| id | w | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|
| core_active_entity_coverage, metrics_weighted_values, metrics_state_digest, metrics_rank_total_order | 5,5,5,3 | instruction.md:9 "Where two authority records amend the same render track inside a single generation, decide from the evidence which of the two the durable state carries, because their recorded order settles nothing." Only evidence: preview-reel seq18/19 pair inside the conformance reference cohort (interval_conformance_fixtures.json, digest 19135) | **implied by a single witnessed case** (rule stated as a question; answer only derivable from one cohort pair) | step 7 (09:53:02, minute 6) settled preview-reel by cohort digest, but treated credits-roll seq28 (authority) / seq30 (migration) gen 44 as sequential; transform.py:101-103 `max(recs, key=seq)` for non-cohort conflicts | the cohort digest only covers cohort tracks; the agent's local fix passed that check, so its self-test was green | **NO, HIDDEN RULE** (who wins is never stated; generalising from one pair is required) | NEW: rule witnessed once in shipped control; close to L1 green control |
| core_preserves_later_amendment | 5 | same, plus positional rollback interval_authority_policy.md:36-46 (target_position one-based into the surviving set, recomputed per op) | cascade through positional addressing | rollback hit credits-roll twice instead of main-program then caption-main | same | cascade | L3 stateful stream |
| reproducer_variant_digest_shift, reproducer_matches_state_digest, composed_equality_under_authority/weighting/reference_map_perturbation | 5,5,3x5 | same rule run on perturbed inputs | cascade | same code | same | cascade | cascade |
| report_rejected_hypothesis | 5 | report must name the falsified transition | judgement field | rebuild_interval_index vs expected replay_encode_journal | none | yes (schema) | cascade from wrong diagnosis |
| verdict_pre_repair_divergence_count | 3 | instruction.md:11 "report how many render tracks diverged ... before your repair" | plain sentence | 3 vs 5 | none | INFERRED cascade | cascade |
| resolution_transition_order | 1 | schema | plain | listed rebuild twice | none | yes | wrong value |
| report_preserves_retired_record, resolution_dependency_order, report_minimal_delta, verdict_authority_anchored_post_replay, verdict_zero_post_repair_divergence, partition_cover_is_disjoint | 3,3,5,5,3,3 | each ends `return ... and _replay_landed(workspace) is not None` (e.g. test 430-436) | **value gate** | fields INFERRED right or partly right; zeroed by the gate | – | gate stated nowhere to agent (internal) | G1 coupling (CL-4) |

## 5 How tests handle QC
- TS-13 ✅ after fix M3 (QC :34): a w3 check asserting integer typing and encoding was split into w3 + w1.
- TS-16 ✅ after fix M1 (QC :32): outcome negatives now require the addressed records correct first, so a reasoning error cannot fire them.
- TS-19 ✅ (QC :175). Risky per our rulings: the same-generation winner is not stated (IN-15/IN-16), yet QC passed IN-15 (QC :117 "every graded rule ... stated plainly enough to act on").
- TS-20 ✅ (QC :176); five w1 checks are schema/encoding.
- TS-26 ✅ (QC :178); stacking: no duplicates.
- IN-15 ✅ QC :117. IN-16 ❌ warn W1 (QC :44, `pre_repair_digest` layer unstated, settled only by an unlabelled number in a shipped report) – deferred because "Each is fixable only by adding a sentence ... which invalidates the recorded trajectory" (QC :26). The agent did not lose on that point.
- AL-28 ✅ QC :91 (max combined 5); stacking flags 23 "UNMATCHED", but by hand the two outcome negatives and R23-R25 are different acts.
- CL-4 ✅ QC :81 ("one-fact-wrong is 69 of 109"); gate concentration accepted at QC :50.
- JD-7 ✅ QC :198 with the note at :51 that trajectory-scoped criteria cannot be exhibited by the oracle.
- Risky per our rulings but passed: G3 hidden share 13.8% (<30%); a 36/109 value gate (our G1 says owned rows); hidden rule implied by one witnessed case.

## 6 Leak avoidance
- W3/W6: instruction.md:9 states that order "settles nothing" and says "decide from the evidence" – names the decision, not the answer.
- W5: only one separating pair (preview-reel) is shipped, inside a cohort whose digest checks the cohort as a whole; the graded instance (credits-roll) is outside it.
- Test comment 271-279: the gate value 1579 "appears in no shipped file" – the key result is never shipped.
- Naming: the cohort file is called conformance fixtures, not "examples"; nothing points from the rule to it.
- LEAK_LIBRARY: avoids "decoy refuted beside use" and "trap spelled out"; risk row CR-3 (one sentence, no alternate reading) is close, but here the sentence is a question so no reading is given.

## 7 Agent behaviour
- Read policy (step 3), ledger (4), journal + map (5), rest (6) in the first minute. Step 7 (minute 6) full analysis; transform.py at step 9 (09:53:55, minute 6.5); build.py step 12.
- Steps 18-23 small edits, not graded logic. Final step 24 at 09:56:47 (9 min run).
- Self-test: cohort digest matched; never checked non-cohort same-generation pairs.
- Final claim vs reality: claims recovery; wrong on the one hidden tie.

## 8 Passed checks
- Focal repair chain (thumb-strip 1883, revisited repair anchors, `_focal_landed` checks): stated stepwise in the policy.
- Schema, encoding, integer and partition-value checks: format.
- Negatives: none fired.

## 9 Take-aways
- RISKY (QC passed, our IN-15 would fail): a rule phrased as "decide from the evidence" with one shipped witness; very effective (Opus generalised from local order instead).
- RISKY: value gate that zeroes a third of the score; QC accepted it as anti-forgery coupling.
- SAFE adopt: outcome negatives that first require the correct handling of the addressed records, so they fire only on cheats.
- SAFE adopt: reproducer graded on perturbations of one input dimension each.
