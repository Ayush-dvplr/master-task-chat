# C_56fe3bdd: ML (Aditya Patel), detection-evaluation engine over a contradictory 100-file estate
T = `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Final_Delivery/56fe3bdd-00c6-5b13-a5c8-90a94ccc475e/`. Run = `T/trajectories/claude-opus-5/run_1/`. Raw extract: `OUT/_extract/56fe3bdd.txt`. Step 1: `A_56fe3bdd.md`.

## 1. Scores and verdict
- Final 61.62 / tests 64.90 (98/151) / rubric 58.33 (42/72). No version skew: 35 ctrf names at test_output.py:5484-5518, recomputed tests 98/151 = 64.90.
- Verdict GENUINE on tests, GENUINE-but-unrequested on the judge.
- Genuine test points lost: 53/151 (baseline_rows_exact 5; detections_r2/r3/r4 15; class_metrics, operating_points, leaderboard 15 as a cascade; reconciliation_counts 3; eval_estate_detections/scoring/reconciliation 15).
- Judge points lost: 30/72, from ten w3 criteria. R5 is tied to a real defect. The other nine are verification acts the instruction never asks for. No negative fired.

## 2. Inventory
- Domain: object-detection release evaluation (vendor GT curation, detection provenance, AP/mAP, release gate). Archetype: data-pipeline with a large domain-calculation core.
- Files seen: 100 files, 78 MB, under /app/data. Formats: csv/tsv/jsonl/parquet/xml/xlsx prediction deliveries per run x node (preds_r{1-4}_n{1-7}), vendor box files (ks/nl/ob batches, plus a reextract), docx policies (data_authority_policy, exclusion_policy, release_governance + a v2_signed decoy, annotation conventions), pdfs (frame_integrity_audit, 179 pages; calibration certificates + a reissue), html registry + mirror, ini aliases, yaml/toml calibration, sqlite stores (rerun store, node6 replica), mbox, ics, delivery_manifest.toml. Governing contract eval_standard_v3.md is 307 KB and annotation_errata_register.md is 498 KB.
- Instruction: 35 lines, ~480 words (instruction.md:1-35). It names the contract, the CLI, 8 output files, the allowed packages, determinism, the run budget, the exactness sentence (:29) and the final-reply contents (:33).
- Tests: 35 checks: 31 positive (151) and 4 negatives (-18). Breakdown: baseline 5, family_t01..t16 5 each (80), detections_r1..r4 5 each, class_metrics 5, operating_points 5, leaderboard 5, reconciliation_counts 3, reconciliation_deliveries 3, eval_estate x5 at 5 each.
- Judge: 34 binary criteria, gpt-5.6-sol, batched. Positives total 72, negatives -16. 22 agent-behaviour trajectory, 5 tool-use trajectory, 3 user_facing_message (R21-R23), 4 negatives.
- Reward: 0.5/151 tests + 0.5/72 judge (reward.toml). Timeouts: agent 14400 s, verifier 7200 s, build 1800 s, 2 CPU / 8 GB (task.toml).

## 3. Core difficulty
A correct engine has to settle authority between near-duplicate deliveries using documents spread over docx/pdf/html. Examples: a short delivery plus a re-extract that may only fill missing partitions; a mirror registry that is valid only for sequences the main registry omits; replica/replay stores routed by rerun_batches.toml. It must then run a long exact chain: GT curation, letterbox inversion from the highest ok attempt, calibration, threshold, class-wise NMS, per-image cap, 101-point AP and the release gate, with no slip.
Class: **computational core plus multi-source authority resolution** (decoys with a governing rule elsewhere, TRUTH.md:183-193). It is not one hidden sentence. It is ~50 planted trap kinds (`_k_*`, test_output.py:1721-2177), each easy alone, chained so that one slip upstream zeroes several whole-file checks.
Why a blind Opus does not finish it in 3 minutes: the contract is 307 KB plus a 498 KB errata register and 100 files in 9 formats. Reading alone took the agent 11 minutes (steps 1-69). The agent got all 16 trap families right (80 points) and still lost the per-run detection chain for 3 of 4 runs.

## 4. Test architecture
- Expected values: a full in-test estate generator `build_estate(seed, scale, id_range)` (test_output.py:258) plus an independent reference `resolve(E)` (:2713). The comment at :4938-4945 reads 'Expected values come from the reference resolution of each estate's source records, never from the agent's files'.
- Tiers: VISIBLE_SEED 734190 at scale 1.0 rebuilds the shipped /app/data, so visible checks need no fixed answer file. EVAL_SEED 6151908437711 at scale 0.12 uses ids 5000000-7499999 and perturbs run quality, plants gate false positives, and adds a class with no GT (EVAL_RUN_QUALITY :1129, EVAL_GATE_FPS :1133, EVAL_NO_GT_CLASS :694, `_fx_release_gate` :2617). CANARY_SEED 90210417 at scale 0.05 uses ids >= 7500000 and is planted at /app/data if absent (:4954-4962, :5101-5108).
- Hidden share: 25/151 = 16.6% (eval_estate x5). This is below our G3 30%, so K5 is KNOWN.
- Visible-family isolation: each candidate image belongs to at most one trap family, and `_visible_family(fam)` grades only that family's rows across 3 artifacts (:5051-5071; TRUTH:205 'one wrong image row costs one family'). This is a per-lever partial-credit design that keeps cascades out of the family band.
- Detections: graded per run with `_visible_detections(run)` on images both sides evaluate, and at least half must be shared (:5074-5098). Scoring artifacts (class_metrics, operating_points, leaderboard) are whole-file exact and inherit any detection error (cascade by design, TRUTH:205).
- Hidden runs: `_hidden()` (:5125-5193) copies the engine and writes the estate at a deep path. It runs 3 times as nobody via setpriv with a random PYTHONHASHSEED and cwd /tmp: twice at the same location for determinism, and once moved for location independence. A strict `_csv_rows` (LF, no BOM, exact header, :5007) and `_same` with type equality (:5035) are used.
- Negatives (polarity-inverted, 'True when the cheat happened'): hardcoded ids < 5000000 (:5430), filename dependence only if runs 1 and 2 agree (:5442), canary ids leak (:5460), nondeterminism (:5472). All honest in the run.
- Tie fixtures place the winning record both before and after the loser (TRUTH:30; `_fx_*_tie` :2447-2549), so neither first-in-file nor last-in-file wins. This is KNOWN as L1-like control.
- stacking_check hints were corrected by reading the code: the visible checks are not 'shipped fixed file' checks. They rebuild the estate at test time.

## 5. Lever table (failed checks)
| id | w | rule | locations | form | agent reading | correct | why self-test missed | stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| baseline_rows_exact | 5 | re-extract fills only partitions missing from the short delivery, with the re-extract's own counts | data_authority_policy.docx s3 (TRUTH:187 table row 'missing partitions only'); delivery_manifest.toml (step 66 shows `nl_boxes_batch02_reextract.csv 57 [... (56,92)]`) | split across files (policy docx + manifest toml) | step 161 `_recover_batch02` slices with the SHORT delivery's manifest count (88 for partition 56) (judge R5 JUST) | take the re-extract partition as declared (92 rows); INFERRED root | the agent's count check (step 75) compared parsers with the manifest per delivery, not the recovered partition with the re-extract manifest | yes, split over 2 files | L4 multi-doc composition; NEW 'two manifests disagree, one per copy' |
| detections_r2/r3/r4 | 15 | one detection source per run and image (rerun store, else assigned node minus quarantine; mirror only for omitted sequences; replica/replay routed by rerun_batches.toml) | TRUTH:11, :187, :191, :193, :364, :366; eval_standard_v3.md s11; data_authority_policy.docx s4 | split across files plus decoys | ROOT UNRESOLVED statically. The agent handles mirror (evalctl.py:1183), quarantine (:2123-2138), replica/replay (:2345-2346) and row run fields (:2116 ff) | reference `resolve` | its own AP recompute (step 148) reused its own detections | yes (TRUTH lists the governing docs) | L4 + L3; NEW 'decoy store with more rows' |
| class_metrics / operating_points / leaderboard | 15 | AP 101-point, operating points, gate | eval_standard_v3.md s12-s14 | cascade | correct method (R20 judge PASS) on wrong detections | n/a | n/a | yes | cascade (K3 amplification) |
| reconciliation_counts | 3 | populations and counts | PES-3 reconciliation section | cascade of batch02/detections | n/a | n/a | invariant check only (judge R9 pass) | yes | cascade |
| eval_estate_detections/scoring/reconciliation | 15 | same rules on the hidden estate | as above | hidden tier | same engine | n/a | image decisions and GT passed on hidden, so the engine generalises except detections | yes | G1/G8 KNOWN |

## 6. Judge architecture and losses
Bands (judge.toml; TRUTH:248, :252-254):
- A. Reading and order (w1): R1 opens eval_standard_v3 deliverable/authority sections before the first evalctl.py; R3 inspects headers/banners of >= 4 suspicious deliveries; R12-R16, R18. All PASS.
- B. Counted inspections (w3, 'at least N files', 'two or more rows'): R2, R4, R6, R17 PASS.
- C. Engine conduct (w3): R8 runs twice and byte-compares; R9 evaluated+excluded = candidates; R20 101-point grid; R28 ignore-region intersection. All PASS. R11 code quality (traj) PASS.
- D. Final reply (user_facing_message): R21 release candidate + decision per challenger (w3), R22 demoted deliveries with rule (w3), R23 checks run (w1). Each quotes the instruction sentence (:33). All PASS.
- E. Negatives: R24 -5 edits /app/data, R25 -5 opens /tests,/solution,/logs/verifier, R26 -3 third-party import, R27 -3 'claims exact without comparison'. None fired.
- F. Independent recompute and exhaustive checks (w3), 10 criteria, ALL FAILED:

| R | wording (short) | class | what the agent did (step) | real? |
|---|---|---|---|---|
| R5 | compares partition-by-partition rows from nl_boxes_batch02_reextract.csv with the manifest | process step, defect-linked | step 66 saw (56,92); step 161 takes 88 | real, matches the test loss |
| R7 | runs the engine on an estate whose file contents differ from /app/data | process (mutated rerun, = our J9) | step 143 `cp -r /app/data /tmp/estate_copy`, an exact copy | real; JUST 'an exact copy' |
| R10 | compares the errata value in each of 4 formats (PDF/Word/MD/HTML) | process, exhaustive | errata alignment of 83 lines in md only (final reply) | real, unrequested |
| R19 | multi-reason exclusion candidates checked against PES-3 s9 | process probe | not shown | real, unrequested |
| R29 | recomputes final detections for >= 1 image of EACH of 4 runs with code outside evalctl.py | independent recompute (our J2) | step 148 independent AP from the agent's own detections, not detections | real, unrequested |
| R30 | 0..1 range check over EVERY prediction delivery | exhaustive property | not shown | real, unrequested |
| R31 | knots strictly increasing for EVERY class of every run | exhaustive property | not shown | real, unrequested |
| R32 | recomputes one operating_points row outside evalctl.py | independent recompute | not shown | real, unrequested |
| R33 | recomputes each challenger decision outside evalctl.py from class_metrics under release_governance.docx | independent recompute | not shown | real, unrequested |
| R34 | inspects one over-cap image and which records were kept | probe | not shown | real, unrequested |

Why QC accepted:
- JD-15 conduct Step 1: every competent route could do these, and they raise the odds, so w3 is a pass (04:92).
- JD-8: the observables are trajectory acts, not files a test compares.
- JD-7: the oracle cannot show any trajectory act. TRUTH:536 'the judged channel is validated, never executed' (K8 KNOWN).
- JD-18 is met by R11.
- JD-11 negatives cover the grader, data edits, imports and false exactness claims.

Shapes that cost a strong agent points without being unfair:
- 'with code outside <engine>' independent recompute of one row per artifact type. Opus recomputes metrics from its own outputs, not the upstream step.
- 'EVERY <file/class>' exhaustive property sweeps. Opus samples instead.
- 'an estate whose contents differ' mutated rerun. Opus copies data verbatim and calls it a relocation test.
- Defect-tracking criteria (R5) that duplicate a known trap as a process act. These lose twice with the test.

## 7. How it passes QC
- IN-15: every negative names an instruction sentence. R24 quotes :31 'Do not modify anything under /app/data'; R26 quotes :13; R27 is a factuality negative tied to the final reply :33. Test negatives cover cheating acts only (hardcoded ids, filename dependence, canary leak, nondeterminism).
- IN-16/IN-17: the instruction states THAT documents conflict and that PES-3 decides (:1 'some of them look more authoritative than they are; PES-3 and the documents it names say which source wins'), not WHICH. W1 is satisfied.
- TS-13: one observable per check (one artifact family or one run).
- TS-16/TS-19: hidden estate ids are in a declared range, and the layout is the same (:3-9 'laid out like /app/data (same file names, different contents)'). Budget is stated (:15, RUN_BUDGET scaled).
- TS-20: core artifacts weigh 5 and are never 1.
- TS-26: the oracle fails only negatives.
- AL-1: every graded rule sits in PES-3 or a named document (TRUTH:292 maps each test to its spec section).
- AL-28: negatives -5/-5/-3/-3 per distinct act.
- CL-4: the exactness sentence :29 'A value that is almost right is wrong, and a row that is right on all but one field is wrong' (FC:491 exemption).
- CL-5: the type is fixed by PES-3 s2 layouts.
- JD-7: oracle-unshowable band F still passed (K8). The risky side is QC_RULINGS JD-7 FAIL (district-heat v1:363) against this task shipping it.
- JD-11 and JD-15 as above.
- Risky and still passed: hidden share 16.6% (our G3 says >= 30%; K5); whole-file cascades on scoring (K3) with the exactness sentence.

## 8. Leak avoidance
- 'It defines every artifact and its exact layout, and it names the document that decides each question' (instruction:1). W10 + LV1.
- 'some of them look more authoritative than they are' (instruction:1). LV7: it announces the coupling, not the trap.
- 'It will be run on other estates of the same layout, so every value it writes has to be derived from the estate it is given' (:16). W9.
- Rules sit in a 307 KB contract plus docx/pdf policies, far from the files they govern (LV5, LV6). The decoy file names (`_reextract`, `_mirror`, `_replica`, `_replay`, `_reissue`, `_v2_signed`) look authoritative. The refuting evidence sits in a different format (TRUTH:183-193). This is the LEAK_LIBRARY 'decoy refuted on same page' row, fixed by putting the refutation in another document and another format.
- No shipped expected output. Visible checks rebuild from the seed (LV3).
- Tie fixtures put the winner both before and after the loser (W7/LV4).

## 9. Agent behaviour
- Start 04:10:03, end 05:22:02 (about 72 min), cost $31.93, 46.9M prompt tokens (result.json agent_execution is None; times from the trajectory).
- Steps 1-69 (04:10-04:19): reads every document type. docx dumps to /app/tmp, pdf via pypdf, html, sqlite, parquet, xlsx. Step 66 prints the manifest partitions including reextract (56,92).
- Step 70 (04:21:18): first full evalctl.py at ~11 min. Steps 71-118: incremental edits on a pickled estate. Step 119 (04:42:59): first full run.
- Self-tests: step 75 parser counts vs manifest (found batch02 5588 vs 5300); steps 141-143 determinism plus a run on an exact copy; step 148 independent AP from the agent's own artifacts; steps 156-161 batch02 recovery investigation that settled on the short delivery's counts; steps 162-194 reruns, leaderboard diff, format, number-parser, IoU and void checks; step 186 attempted pyflakes (not installed).
- Graded logic changed after the first program many times (steps 71-161). The batch02 change at step 161 introduced or kept the 88-row reading.
- Final claim (step 198): release candidate R3, populations 12442/12318/9032, 'Checks run' lists parser-vs-manifest, errata alignment, parse coverage, and geometry and IoU cross-checks. It claims nothing false (R27 not fired). Reality: 3 of 4 runs' detections are wrong.

## 10. Passed checks and criteria
- Tests: all 16 trap-family checks (80 points), detections_r1, reconciliation_deliveries, eval_estate_image_decisions, eval_estate_ground_truth. Each family is a stated rule tested in isolation (TD4 KNOWN: Opus passes per-rule fixtures, even with 50 kinds).
- Judge: reading-order, counted-inspection and final-reply criteria (bands A-D), all naturally done by a careful agent. Final-reply criteria quoting an instruction sentence are free points.

## 11. Take-aways
- SAFE, NEW: per-family visible isolation (each image carries at most one trap and is graded only in its family). It gives clean partial credit per lever and confines cascades to the pipeline checks. Reusable as 'one planted lever per record, graded per lever family'.
- SAFE, KNOWN (TD1): an in-test estate generator rebuilds the shipped data from a seed, so there is no fixed expected file and the hidden estate shares the layout.
- RISKY, NEW: duplicate deliveries with two manifests (the short copy's and the re-extract's) that disagree on one partition. It is determinable but split across a policy docx and a toml. It is strong because the agent saw both numbers (step 66) and picked the wrong one.
- RISKY (K3): long chains with whole-file scoring checks. 15 cascade points from an unresolved upstream slip. They pass QC with the exactness sentence, but they amplify one slip.
- Judge, SAFE: 'recompute with code outside <engine>' for ONE row of each artifact type, at w3. Opus checks invariants and its own artifacts, not independent recomputes.
- Judge, RISKY: 'EVERY <file/class>' exhaustive sweeps. They are odds-raising per JD-15, but they read as preference. Keep them at w1-3.
- Technique: a canary seed planted at /app/data if absent, plus an id-range negative, catches engines that read the shipped estate at run time.
- Avoid: a hidden share below 30% (16.6% here), and judge criteria that duplicate a tested trap as a process act (R5 double-charges one defect).
