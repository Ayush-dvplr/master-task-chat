# S3a vendor-archive-roundtrip-recovery round outputs

Paths (prefix master_chat_work/):
- VB = 20261021_vendor-archive-roundtrip-recovery/build/BUILD_REPORT.md
- VH = 20261021_vendor-archive-roundtrip-recovery/hardness_r1/HARDNESS_REPORT.md
- VT = 20261021_vendor-archive-roundtrip-recovery/baseline_v0/TRAJECTORY_RESULT.md
- VR = 20261022_vendor-archive-roundtrip-recovery/rebuild_r1/REBUILD_REPORT.md
- VD = 20261023_vendor-archive-roundtrip-recovery/harden_lp1_r1/DIAGNOSIS.md
- VL = 20261023_vendor-archive-roundtrip-recovery/harden_lp1_r1/HARDEN_REPORT.md

## Build (VB)
- VB:42 "Hidden-weight share 0.83. Every counted lever is HIDDEN-ONLY" (claimed). Auditor VH:9 found LV2, LV3, LV5 DERIVABLE; VH:73 "The builder's claim that W-VA2 'passes its own round-trip on the visible captures' is false: 4688 visible captures carry extensions".
- VB:75 tests_qc A3 WARN 48 checks over the 35 cap.
- VB:95-98 OPEN CONFLICT Q18 TRUTH provenance authored_by vs DS-27.
- VB:102 Docker Step 10 not run; VB:107 baselines left to P3.

## Hardness r1 (VH)
- VH:9 "Verdict: REBUILD. S4 = 0.648 ... S4b = 0.966, S2 = 0.276, best shortcut = 0.221".
- VH:46-47 "This S4 assumes a careful agent ignores four rules that are each stated in plain words, so it is a generous lower estimate ... A real careful run probably lands between 0.65 and 0.97." (Real: 0.8897 corrected v0, VT:17.)
- VH:49-51 "CR1 (LV5 x LV6) is the only natural two-rule failure ... Every other composition check is a conjunction of independent rules, so a solver right on each rule is right on the composition." -> conjunction != interaction (study rule 6 nuance).
- VH:94-96 composition share 0.228, "S4b loses only 5 of those 33, so they are conjunctions, not interactions."
- VH:87 "report_roundtrip pays a fabricated report: it checks only internal consistency".
- VH:101 immune checks 40 points paid by every reflex.
- VH:106-110 V1 contract vs verifier cumulator disagreement (bundle bug) -> agent lost basic_delta, va1_cross_delta (VT:17 "raw-frame running-total contract bug from P3").
- VH:111-115 V2 hidden encode inputs invalid decode docs (value: null) — bundle bug.
- VH:116-119 latent decode_stream ignores stream_id; TRUTH says 6 negatives but 5 registered; seeds unused.
- VH:172 "Arithmetic warning: even after F3, S2 keeps 24 visible points."

## v0 trajectory (VT)
- VT:6 tests 4.83% INVALID; VT:11-12 0600 NamedTemporaryFile + setpriv nobody => agent decode printed unreadable_input; two negatives fired because temp path differs per call ("15 - 8 = 7").
- VT:13 "vendor-archive's tests have 0 chmod calls; the other 3 bundles do chmod".
- VT:14 "Never caught before: the builder and P3 ran rewardkit as a normal user (no setpriv); Docker oracle (Step 10) was not run."
- VT:17 real agent work 129/145 = 88.97%; lost only V1-bug checks + va4_overlong_bytes + report_decoded_examples. VT:7 rubric 100% (36/36).

## Rebuild r1 (VR)
- VR:9 kill-by-uid race: "Without the lock, the uid sweep killed other checks' live runs, and the first Docker pass scored the oracle between 0.11 and 0.22." (same as schema 0.207/0.281).
- VR:28-33 rows 11,12,15 kept "with a different design, which conflicts with the recheck. validate_bundle.py now runs strict by default and FAILs 11.2, 11.3 and 11.5 without these negatives" -> CONFLICT recheck vs validator.
- VR:49 row 26 "validator 7.2 FAILs without SAMPLE_SEED, CHALLENGE_SEED, EVAL_SEED, `_write_corpus`" -> CONFLICT.
- VR:56-62 redesign: no rule count, 70% whole docs, schematic example, RUN split across 2 files, omission, decoy loader_notes.md.
- VR:99 design probe 10 wrong readings.
- VR:121 forgery 0.0. VR:134 local harness clone at c9e3454a, not pulled (read-only git).
- VR:138-143 judge R1-R4 figures from shipped streams; VR:147 R5/R6 cheap-to-meet.
- VR:150 judge, real trajectory, PL QC not run.

## a2 real trajectory diagnosis (VD) — after rebuild + P12 rounds: 100/100/100
- VD:4 tests 100.0, rubric 100.0, combined 100.0. VD:6 genuine.
- VD:12 41 steps, 11 minutes (of budget).
- VD:13 steps 2-7 read every spec in full in first 30 s, xxd dump.
- VD:14 steps 8-11 profiled tables, found generator patterns `<prefix>_%04d`, aliases `name@s<id%40+1>`, baked tables as 2100-byte blob (agent infers generator rule from data).
- VD:15 step 12 (3 min 17 s) wrote decode.py in full; VD:18 "After the first write it never changed the logic that the grader checks."
- VD:17 steps 25-32 self-tests: full catalog round trip, header ordering, injected damage salvage, hand-built stream, overlong re-encode, CLI from temp dir, fuzz of 6000 cases.
- VD:25 RUN leaked: "Rule stated next to its use; the shipped stream 3 ... is a separating example; the judge R1/R2 ask makes the agent compute it".
- VD:26 REV decoy leaked: "The decoy is refuted in plain words on the line that uses it; the final reply says 'Per the contract (which overrides loader_notes.md)'". (decoy refuted beside use = leak; same as district SIGNEDY.)
- VD:27 REMAP leaked "procedure is numbered"; VD:28 STATE leaked "exception is written as its own sentence" (OMISSION lever leaked because the exception sentence is explicit).
- VD:29-30 ESC/SALV "W1 violation: the trap is explained"/"both reflexes are named".
- VD:31 ENC "Stated twice; checked by the agent's self-test".
- VD:32 REJ numbered list; VD:34 judge figures from shipped files.
- VD:36-42 common cause: "Every rule sits in one plain sentence beside its use ... No rule has a plausible second reading ... The hidden fixtures only repeat rules the agent had already coded at step 12 ... the a2 program is oracle-equivalent on all 24 checks."
- VD:44 "PRIMARY CAUSE: levers too weak by design (cause 4). No artefact ... our QC rounds put no new figure or rule in front of the agent."

## Harden lp1 r1 (VL)
- VL:6 a2 program scores 0.1682 on new tests (reflex replay, not fresh agent).
- VL:11-13 new levers: L2 count unit unsigned behind value_sum control; L6 cumulator per field name (Terms definition); L3 run ledger with resends; L5 JSON boolean override/integer length beside trim rules. "Shipped data separates the lever: no, except L5's string override row".
- VL:19-23 whole docs 60.7%, isolated+mutation 28.0%, shipped-only 2.8%.
- VL:26 "The instruction no longer asks for figures and states 'Each output document is graded whole on fresh inputs.'"
- VL:52 G7 messages not in ctrf (rewardkit 0.2.1 no message field; tests_qc B4 fails writes under /logs/verifier) -> kit-tool conflict.
- VL:53 oracle x3 per Ayush, kit asks x5 -> CONFLICT.
- VL:54 judge R1-R4 conduct criteria oracle cannot meet (JD-7) accepted.
- VL:55 "No real trajectory was run. The 0.1682 is the a2 program's reading, not a fresh agent's. A careful agent that reads Field names, Terms and Runs can code all four rules, and the levers depend on misreading."

## Derived (for FINDINGS)
- V-a: build-time S4 0.648 vs real 0.8897 (under-predict 0.24), real a2 1.00 after rebuild that had been designed for <0.20 (the rebuild design 70% whole-doc + split + omission + decoy still scored 100) => study rule 4/5/6 insufficient when each piece is still one plain sentence, and a shipped separating example exists. High confidence.
- V-b: decoy refuted beside its use leaks (vendor REV + district SIGNEDY).
- V-c: omission lever leaks when the exception is its own sentence ("No other frame moves the cumulator, except reset").
- V-d: agent reverse-engineers generator patterns from shipped tables (VD:14) -> hidden inputs must keep tables or the program breaks; and patterns in synthetic data are visible.
- V-e: agent self-test battery includes fuzz 6000 cases and round trips: any lever whose wrong reading fails a self-roundtrip is DERIVABLE (VH:73-74).
- V-f: bundle bugs: 0600 perms (VT), V1 contract/verifier mismatch (VH:106), V2 invalid fixtures, kill-by-uid race (VR:9). Each cost real points or oracle.
- V-g: conflicts: recheck vs validator 11.2/11.3/11.5 and 7.2 (VR:28,49); oracle x3 vs x5 (VL:53); G7 vs B4 (VL:52); Q18 VB 15.5 vs DS-27 (VB:95).
- V-h: judge figures computed from shipped files are free points (VD:34: 20 of 24 judge points).
