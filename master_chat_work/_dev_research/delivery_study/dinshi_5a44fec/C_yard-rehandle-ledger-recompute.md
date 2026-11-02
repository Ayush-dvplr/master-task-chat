# C card: yard-rehandle-ledger-recompute

Base `T=.../Perfect_for_Delivery/Dinshi_Jain/yard-rehandle-ledger-recompute`. QC report `Kunwar_Singh_yard-rehandle-ledger-recompute_QC_Report.md`.

## 1 Scores and verdict
- Recorded overall 48.91, tests 16.42 (11/67), rubric 81.4.
- Verdict **PARTLY** (A file). The recorded program tier (10 `program_*` checks) failed because of a permission bug in the pre-fix verifier: QC :34 F1 "all ten `program_*` checks returned False on a correct submission". QC re-grade of the same artifacts: **47/68 = 0.6912** (QC :74).
- Genuine test points lost: **21/68** = shipped_vessel_family_exact 3 + shipped_manifest_exact 3 + program_{strained,wide,sparse}_vessel_exact 3x5 (QC :74 "the remaining 21 weight of loss is a genuine error confined to the vessel family and the manifest that digests it").

## 2 Inventory
- Domain: container-terminal yard shift recompute (rehandles, quay ration, vessel load). Archetype: **multi-stage spec pipeline** (14 stage specs) + office papers (xlsx/pdf/docx) + decoys + reusable program run on freshly minted shifts.
- Data: 59 files. spec_stage_y01..y14 md (1-5 KB each), output_schema_reference.md 12 KB, serialisation_and_digest_contract.md, yardledger_program_contract.md, worked_examples.md (invented shift, form only), known_traps_and_footguns.md 1.6 KB, policy toml/yaml (8), xlsx 30 KB (six sheets, one live by key cell), pdf memo 14 KB, docx 3.8 KB, sqlite audit db (decoy), box_class_supplement and legacy_tariff_extract (decoys signposted by data_lineage.md), operational_exception_notices.csv with prior-shift rows.
- Instruction 750 words; 39 documents + `/app/out/yardledger.py`; 14400 s.
- Tests (stacking_check, current): 34 checks, positive 68, negatives -62 (16: 8 wrong-reading + cheat negatives). Judge 40 criteria, positive 91, batched. Reward = (tests + rubric)/2.

## 3 Test architecture
- Expected values: **reference at test time on reseeded generated corpora**. Whole corpus generator inside tests/test_output.py (`mint_instance` 279, `_mint_*` 312-1011, office-file writers xlsx 1131 / docx 1214 / pdf 1261 / sqlite 1308, `write_stage_specs` 3066 regenerates spec text per corpus, `mint_corpus` 3830) and a full independent reference pipeline (stage_y01 4308 ... stage_y14 5267, `publish` 5354-5716, `run_pipeline` 5716). QC F4 (:37) made the oracle's Y13 independent of the tests (59% -> 3% overlap).
- Hidden vs shipped: SAMPLE_SEED = shipped shift; MINTED_SEEDS = three profiles strained / wide / sparse, never shipped.
- Execution: `_grant_read` 5852 (QC fix), `_run_program` 5915 passes the two options in reversed order on the graded run (tests "either order" promise) and neither run pre-creates the out dir.
- Partial credit: **document families**, each a byte-equality check via `_compare` 5992. `_shipped_family` 6018 docstring: "Each family stands on its own. A document read the wrong way costs the family it sits in and nothing else, so partial credit tracks how much of the shift was recomputed." Families: SPINE 14 docs, STATE 6, YARD 5, VESSEL 12; manifest a separate w3 check (`_body_shipped_manifest_exact` 6110).
- Program tier: minted spines (one check, all 3 seeds, w5) + per seed state / yard / vessel (9 x w5) via `_program_family` 6130 = 50/68 = 73.5% hidden. stacking_check reports these as "isolated 73.5%"; by hand they are the hidden reseeded tier.
- **Wrong-reading negatives** (8): `_matches_variant(name, {hook: override}, files)` runs the in-test reference with ONE hook swapped for the wrong reading and fires if the agent's listed files equal that variant byte for byte (e.g. `_ration_budget` -> 400 for "run to convergence"; `_ration_quantise` identity for "round once at end" 6277; `_ration_cell_key` -> one cell for "redistribution across the pairing"). Cheat negatives: hardcoded -5, reads_training_corpus -5, nondeterministic -3, filename -3, rebinds_verifier_dependencies -3. None fired.
- Mutation tests: none in the strict sense; variation comes from three generator profiles.

## 4 Lever table (failed checks, genuine part only)

| id | w | rule graded | locations (quotes) | form | agent reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|
| shipped_vessel_family_exact | 3 | 12 vessel documents byte-exact (reference `publish` 5555-5716; stage_y13 load 5195-5260) | Spec: spec_stage_y13_quay_ration.md Y13.9-Y13.11; docx directive (stowage keys, class ranks, bay register "A bay the register does not carry takes the band of the highest numbered bay below it") | not determined (static only; reference cannot be run under READ ONLY) | agent's departure order equals sort of its own manifest by (rank, stow, bay, box) for all 6 vessels (my read-only check), deferred box VS-129 CTR-1846634 assessed 0 published 1600 | agent inspected spine docs (steps 49-60) and checked headers; no independent check of vessel docs | UNDETERMINED. QC M1 (:57-63) Reading B ("cap did not bind" strict vs <=) costs spine as well, and the agent's spine passed, so it is not that ambiguity (INFERRED) | INFERRED one-document error (QC :107 "one wrong value scores 0.912 (62 of 68, losing shipped_vessel_family_exact 3 and shipped_manifest_exact 3)") |
| shipped_manifest_exact | 3 | manifest digests every document | serialisation_and_digest_contract.md | cascade of the vessel error (manifest hashes vessel docs) | same | same | stated | natural cascade (CL-4) |
| program_{strained,wide,sparse}_vessel_exact | 3x5 | same vessel family on three minted shifts | as above | same error repeated on hidden seeds | same | same | as above | G1 amplification via per-seed family |

Artefact part (not a lever): 10 program checks x5 minus the vessel three = 35 points lost to the permission bug (QC :34, :74).

## 5 How tests handle QC
- IN-15 ✅ (QC :143). IN-16 ❌ minor M1 (QC :144; spec_stage_y13_quay_ration.md:56-57 "members of that cell whose target the cap did not bind"; equality case unsettled). QC drafted a clause "A vessel whose target equals its ceiling is bound by that cap and receives no freed minutes." and reverted it at the tasker's instruction (QC :26, :63), accepting a known minor ambiguity to keep the trajectory valid.
- TS-13 ✅ after M5 (QC :46: parse split from line endings). One check = one family of documents, which QC accepts as one property.
- TS-16 ✅ after F6/F7a (QC :39: filename negative re-raises if the renamed run cannot complete). **Risky per our rulings**: 8 wrong-reading negatives penalise a reading, not a cheat. Our TS-16 / G4 (negatives only cheating acts) vs QC :117 "The eight wrong-reading detectors remain mutually exclusive by exact-match construction and the cheat detectors defer explicitly." It passed QC because each fires only on an exact match with a named wrong-reading output.
- TS-19 ✅ (QC :201). Minted profiles stay inside the generator's own bounds.
- TS-20 ✅ (QC :202): families 3, program 5, hygiene 1.
- TS-26 ✅ (QC :204): families are disjoint document sets; manifest separate.
- AL-28 ✅ after F7 (QC :261; :40 nondeterminism pair separated; judge R30 narrowed to hand edits). stacking_check groups the 8 wrong-reading negatives as one UNMATCHED act; by hand each is a different act.
- CL-4 ✅ (QC :247, :107): one wrong document costs 6/68 on shipped; with program tier one wrong family costs 3+3+15 = 21.
- JD-7 ✅ (QC :224).

## 6 Leak avoidance
- This task does the **opposite** of W1: the Y13 spec names wrong readings outright, e.g. "Redistributing across the whole pairing rather than inside the cell is wrong and gives different shares" (y13 :60-61), "a ration that carries exact shares through every pass and rounds once at the end is a different ration and gives different numbers" (:72-74), "The budget is a count, not a test ... not run to convergence" (:82-86), "The load is a sequence and not a selection" (:107-108). Each is paired with a wrong-reading negative. Opus obeyed all of them (no negative fired, spine passed): explicit trap sentences give zero yield and match LEAK_LIBRARY ESC/EXT and SALV ("explains trap", W1).
- W2/W8: data_lineage.md signposts the decoys (QC CL-6 :109), one neutral line each.
- Office papers: live sheet chosen by a key cell matching the shift reference (W3 plain form; no separate trap text). Opus selected it correctly.
- worked_examples.md uses an invented shift (form only), so no example where readings differ (W6).
- known_traps_and_footguns.md exists as a file of named traps (W1 violation by design); Opus read it in the first minute.
- Comparison: our RUN / SALV rows leaked by explaining the trap; here the explained traps also yielded nothing. The only genuine loss is in a part the spec does not flag.

## 7 Agent behaviour
- 80 steps, 24 min (11:21:01-11:44:53 UTC). Steps 2-9 read readme, overview, lineage, sentinel, all 14 specs, schema, serialisation, program contract, worked examples, policies (first 33 s); 10-18 office papers by 11:22:20; 19-38 data exploration.
- First full program: step 39, 11:35:04 (minute 14). Steps 40-45 and 61-63, 75 fixed details (confirmation by_order, sheet label value, event key). No change to the Y13 ration logic after step 39 (INFERRED from edit targets).
- Self-tests: run on shipped data, inspected terminal_reconciliation and ration trace (49-60), schema headers (58), input md5 before/after and two-run byte identity (69-72, 76). No independent recompute of vessel documents, no synthetic shift.
- Final claim (step 79) that the shift is recomputed; reality: spine/state/yard right, vessel family wrong; program generalised (QC re-grade).

## 8 Passed checks
- Spine 14 docs, state 6, yard 5 on shipped and on all three minted shifts (QC re-grade): every stage where the spec spelled out the wrong reading, Opus took the right one.
- Hygiene (artifacts exist, parse, line endings) and all negatives: trivial for a careful agent.

## 9 Take-aways
- SAFE adopt: whole-corpus generator inside tests with several named profiles plus an independent reference pipeline; families graded byte-exact so one wrong document costs one family.
- SAFE adopt: graded run passes CLI options in a different order from the documented one to test an "either order" promise.
- RISKY: wrong-reading negatives matched against a hook-swapped reference; QC accepts them only with exact-match exclusivity, and they yield nothing when the spec names the wrong reading.
- Avoid: spec sentences that name the wrong reading ("X is wrong and gives different numbers") and a traps file; Opus obeys them.
- Avoid: shipping a verifier that runs the delivered program without a read grant (cost 35 points of measurement).
