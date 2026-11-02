# Conflicts

Each entry gives side A, side B, the source of each, current status, and the findings involved. Paths are relative to `/Users/mac/Desktop/Terminal Bench/` unless absolute. "kit" = `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

## A. Our rules against each other (process churn)
**X1. Score gate wording, changed four times; an old version is still live in notes.** Status: resolved in decisions, but the batch notes are stale (F-35).
- d3 set overall <30, later superseded. d15 set tests <0.20. d23 E1 set "per-run gate test<90 rubric<90 overall<30".
- d63 set "TEST-PHASE GATE tests<100 rubric<100 overall<70", and d83 resolved to the same (`master_chat_tasks/decisions.jsonl`).
- `prompts/issued/_adhoc/20261022_converted_batch_notes.md` l29 still says "per-run gate tests < 90, rubric < 90, overall < 30".

**X2. chmod 755 → 700 → 755.** Status: resolved to 755, after two rounds of churn (F-36).
- d48 (Q36 option A) chose chmod 700. d51 (Q39) chose 755, superseding it (upstream 2690e960).
- KNOWLEDGE.md l75 and l81 carry both versions.
- log.jsonl l71, 72, 76 and 88 show the edits.

**X3. Design target against real results.** Status: open. Every design target was missed (F-65, F-30).
- DESIGN targets are 0.10-0.20 (vendor DESIGN:4, dispatch :21, schema :192, sensor :17).
- Real results were vendor 88.97 → 100, schema 99.3, district 100, cohort 100 (VD:4, schema TRAJECTORY_RESULT).

**X4. Build-time solver prediction against real runs.** Status: d49 (Q29 option C) temporarily skips the solvers. They have not been replaced by a calibrated predictor (F-30).
- S4 predictions: emberforge 0.168, schema 0.627, vendor 0.648.
- Real runs: 0.942, 0.993, 0.890 (round_notes l12: "S4 wrong by 0.25-0.77").

**X5. Reflex replay used as a difficulty figure.** Status: open (F-31).
- d77: "every P12 re-runs reflex, compensate if >0.20".
- The reflex replays the OLD agent program on NEW tests (VL:6, C4:52-54). log l160: trap survival not re-measured.

**X6. Stacking measurement.** Status: d87 made no change, so two definitions are still in use (F-63).
- stacking_check counts isolated + mutation.
- LEVER_RULES G3 counts isolated-only (d87).

**X7. HIDDEN-ONLY label against real leaks.** Status: open. The label measures data, not text (F-13).
- district DESIGN.md:312 "every lever HIDDEN-ONLY on the data"; vendor LEVERS.md:75 "Each counted lever is HIDDEN-ONLY".
- Both tasks scored 100 in real runs (DHL, VD:4).

**X8. Prompts against bundles on the judge key.** Status: a factual error, repeated three times (F-37).
- The prompt said "no judge key".
- C1:6-8 "prompt said no judge key; file says otherwise"; D1:13 the judge did run; C3:17 "The master note says it did not, and that is wrong".

**X9. Oracle repetitions.** Status: open, no written resolution (F-59).
- Kit / Final_checklist: oracle ×5.
- Ayush: ×3 (KNOWLEDGE.md; VL:53; dispatch p12_r2 PL_NOTE; vendor p12_r2).

## B. Our hardness doctrine against QC rules
**X10. Hardness must be undiscoverable, but QC requires discoverability.** Status: structural. Resolution: hardness has to come from interactions of stated rules (F-55, F-58).
- Doctrine: hidden-only levers work. d18 sets "A hidden composition"; L14 records "only held lever ... hidden-only".
- QC: kit 01:39 IN-9 "licence to withhold ... must still be discoverable from the shipped data". 05:24 AL-4 "undocumented edge cases carrying graded weight in either layer). Fail."

**X11. "No plausible wrong reading" against IN-16.** Status: resolvable. A lever must be reflex-plausible but textually indefensible (F-58).
- DIAG lesson: the cause of leaks was "No rule had a plausible wrong reading" (C3:57).
- kit 01:46 IN-16 fails "two readings that a competent practitioner could both defend". IN-16 is cited in all 20 QC_2026-10-21 reports and all 33 QC assigned reports. In emberforge v1.md:34, the IN-16 + AL-4 findings hit LV-EF-1 = L7 restated.

**X12. Study rule 6 against TS-26 / AL-28.** Status: d74 keeps the cascade, built so that it passes QC (F-64).
- Study rule 6: dependent chain plus whole-document grading, with isolating checks ≤30% (round_notes l18).
- kit 03:53 TS-26: "No intra-test double payment, in ANY pairing".

**X13. QC fixes trade away hardness.** Status: open; no policy for refusing a hardness-reducing fix (F-56, F-38).
- Lever designs need ambiguity-free but rare interactions.
- 7ef8d80a triage_v2: "3 up, 10 unchanged, 6 down". 07d51b69: "1 ↓ (JD-15, H4)". caldermoor v3: "↓ small 4". vendor QC_DEFENCE:191 "loses some bite". Every harden round reopened QC: district v4 FAIL 4/3/1, vendor v5 MINOR 0/3/3.

**X14. Conduct criteria.** Status: accepted (d74). Their cost to the rubric channel is UNVERIFIED (F-57).
- JD-7 conduct criteria were accepted (d74). kit 04:86 JD-9: "Prefer trajectory/state_change criteria that watch HOW the agent worked".
- These criteria pay the careful agent's habits: district QC_DEFENCE:128-130 R1-R4 "builds its own ... and compares"; caldermoor R1 staging. That works against the rubric <100 aim.

## C. QC rules against each other
**X15. TS-13 against TS-23.** Status: rule trap (F-52).
- kit 03:44 TS-13 "One property per test". kit 03:62 TS-23 "at most 35 (warn)".
- Splitting tests made schema "marginally easier (+2/137)" (schema p12_r1). District p12_r2 kept 38 tests because merging would violate TS-13. QC_DEFENCE D10:136.

**X16. JD-5 against JD-18.** Status: rule trap; a schema RECHECK row was marked UNSURE (F-53).
- kit 04:71 JD-5 (compound). kit 04:99 JD-18 (multi-facet definition).
- schema recheck_r1 row 10 cites 04_Judge_QC.md:71 against :99. district p12_r2 JD-18 R9: weight 1 against the QC proposal of 3, compound.

**X17. JD-9 against F1/F3.** Status: no neutral fix exists (F-54).
- JD-9 flags figure criteria.
- caldermoor triage_v3: "the gate would flag it again. No neutral change exists: adding process criteria is barred by F3, removing figure criteria by F1".

## D. QC rules against the kit and tooling
**X18. AL-20 / B4 against kit-mandated blocks.** Status: QC false positives (F-51).
- AL-20 flags `curl|sh`; the TS-SCRIPT-B4 deny-list regex flags anti-cheat token lists.
- That block is required by kit 02_Data_Solution_QC.md:120-144 DS-29. B4 fails 12 of 13 converted tasks, and CONVERSION_SUMMARY.md:37-38 says "Editing them would change grading".

**X19. G7 ctrf messages against rewardkit 0.2.1 / B4.** Status: workaround; the `[check]` lines go to test-stdout instead (F-61).
- G7 requires failure messages in ctrf.
- rewardkit 0.2.1 has no message field; normalize_ctrf.py drops it; tests_qc B4 forbids /logs/verifier (VL:52; district QC_DEFENCE:132-133).

**X20. validate_bundle against the QC recheck.** Status: dead negatives kept to satisfy the validator (F-60).
- validate_bundle 11.2/11.3/11.5 and 7.2 FAIL without the negatives and seeds.
- RECHECK and TS-16 flag them as dead (VR:28-33,49; vendor p12_r2 TS-16).

**X21. VB §15.5 against DS-27.** Status: d16 says conflicts are reported, not picked. Still open.
- VB §15.5 sets the provenance layout.
- DS-27 requires the opposite (d16; schema BUILD_REPORT:173 "OPEN CONFLICT Q18").

**X22. Style findings against kit layout freedom.** Status: QC false positives, rebutted (F-48, F-49).
- W-01-1 flags short lead lines as slop. JD-16 R9 was flagged.
- kit 01_Instruction_QC.md:19 makes layout the author's choice (emberforge p12_r1 RECHECK_FIX:14). JD-16 R9 is rebutted by 04_Judge_QC.md:97 (emberforge p12_r2 RECHECK_FIX:11).

**X23. Mixed kit versions within one batch.** Status: tooling gap (F-69).
- The kit sync (e405488540/601b708ade) was applied to 12 converted tasks.
- season-ladder was not updated (CONVERSION_SUMMARY.md:103-105).

## E. PL answers against results
**X24. "Levers alone are not enough".** Status: confirmed by results, and the doctrine is unchanged (F-08, F-11).
- d73 / feedback l3: "frontier models solve any direct task".
- Our own designs still stated every lever in one plain sentence: VD:36-44 "PRIMARY CAUSE: levers too weak by design"; C3:57-62.

**X25. "Fix every issue before the trajectory" against measuring hardness first.** Status: open; ordering not reconsidered (F-32).
- d55 (QL) says fix every issue before the trajectory.
- L54: all 3 tasks scored 100 after the QC polish. Difficulty was never measured before the polish.
