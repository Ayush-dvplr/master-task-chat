TRIAGE (W1-029, 3 Nov 2026): review list for Ayush built from tmp/W1-027/FOLD_TABLE.md

Sources: rows whose proposed action is "add to RULES_IN_FORCE" or "ASK AYUSH" (120), plus the 13 design detail CONTRADICTS rows (12 already in the first set, F275 added), plus the rows of the SUMMARY paragraph "Conflicts inside the active files" not yet taken (F246, F301). RIF:N is a line of drafts/P1/RULES_IN_FORCE.md. File names as in the FOLD_TABLE key. Each row sits in exactly one item.

COUNTS
1. Rows taken: 123
2. Items after merge: 59
3. COVERED: 3 items (5 rows)
4. DECIDED: 10 items (20 rows)
5. REVIEW: 46 items (98 rows) in 7 batches

COVERED (one line): F101, F369, F370: authority order (route 1 R0 or pipeline_v4/PLAN.md wins): covered by the state card rules header ("the only rule text the master follows") and MASTER_RECOVERY.md Part A steps 1 and 6 | F368: questions older than 12 h first: covered by the state card WAITING FOR AYUSH section (oldest first, over question_age_hours 12 = raise now, settings.json) | F119: L2 held out instances firing a documented branch: covered by RIF:10, it is PATTERNS D1

DECIDED (one line): F18, F104: primary kinds (a), (b), (c) only: Q123 (R25, primary from PATTERNS.md DESIGN families) | F21, F105, F292, F121: timeout or crash as primary with no cap or 10 to 30 percent: Q123 (CR1, timeout only an extra unless Ayush says so) | F103: the primary lever is lost by the careful exact program: Q123, KEEP until CR2 | F131, F132: "bypass" quote and its gloss: Q125 (quote dropped, fix map) | F245: edit tests or judge "in a form QC accepts": Q125 and Q126 (fix map) | F267, F294: QC safe form table: Q125 (becomes part of the fix map) | F333: oracle x3 report line: Q125 and Q126 agreed line check | F186, F306, F392: repos it may read (add master-task-chat): R34 as suggested (RULE_REVIEW.md:126, ANSWERS.md:329 to 331); only copy the list into RIF:14 | F226, F281, F92: old QC pass definitions (zero fails with minimal minors; fix every minor): Q122 deletes the old QC pass definition, RIF:7 (R18) holds; the order part of F92 goes with T24 | F177: trap survival at most 2 tries then PAUSED: Q122 deletes round caps, RIF:8 (R15)

BATCH 1. LEVERS AND DESIGN (11 items)
1. T1. Sources: F7 LEVER_RULES_v3.md:40; F26 LEVER_RULES_v3.md:95.
   Rule: pick one primary Shape (B or D) and combine S1 or S2 with S3, S5, S6.
   Suggestion: DROP. Q123 already takes the primary lever from PATTERNS.md families; keep Shapes and S codes as background how to text only.
2. T2. Sources: F8 LEVER_RULES_v3.md:42; F49 LEVER_RULES_v3.md:164; F57 LEVER_RULES_v3.md:172; F275 KNOWLEDGE.md:7.
   Rule: each lever at least 25 percent alone, at least 70 percent of weight on hidden corpora, all but one row under 70.
   Suggestion: DROP. old numbers against RIF:9 and RIF:10 (Q122); keep "at least one hidden rerun per output family" as how to text.
3. T3. Sources: F12 LEVER_RULES_v3.md:86.
   Rule: stated rule levers (L1 to L11, S, H, T) are PAUSED until the lever audit.
   Suggestion: CHANGE. "Misread rule levers are allowed under CR7; the other paused kinds stay paused until the lever audit." CR7 is confirmed by Q123, the audit is still owed for the rest.
4. T4. Sources: F25 LEVER_RULES_v3.md:93.
   Rule: rejected sources include odd carriers and format rules.
   Suggestion: CHANGE. remove "odd carriers and format rules" from the rejected list, since carrier variation is PATTERNS D2; the other rejected sources stay how to text.
5. T5. Sources: F120 20261101_route1_notes.md:34.
   Rule: LC1 bounded induction is an allowed lever form.
   Suggestion: CHANGE. "Bounded induction counts under PATTERNS D1 only when the finite family is stated or shown in the shipped files." It is not a family of its own.
6. T6. Sources: F10 LEVER_RULES_v3.md:58.
   Rule: L11 evidence induction is a pilot, not required.
   Suggestion: DROP. paused by LEVER_RULES_v3.md:86 and not a PATTERNS family.
7. T7. Sources: F3 LEVER_RULES_v3.md:33.
   Rule: a degenerate shipped instance may hide a case, never the rule sentence for a branch it hides.
   Suggestion: KEEP. "A shipped instance may hide a case, never the rule: every hidden branch has its sentence in the docs." Same spirit as CR7 and Q126; decide together with R28 (Q116).
8. T8. Sources: F316 state.json:62.
   Rule: hardness lives mainly in the instruction or task; traps genuine.
   Suggestion: DROP. vague and overlaps R28 (open) and the PATTERNS families; R28 settles where difficulty comes from.
9. T9. Sources: F32 LEVER_RULES_v3.md:146.
   Rule: "no rule counts" joins the no "note that", no trap list list.
   Suggestion: KEEP. add to RIF:10: "no rule count"; telling how many rules exist announces the trap.
10. T10. Sources: F23 LEVER_RULES_v3.md:91; F109 20261101_route1_notes.md:11.
   Rule: every lever names oracle branch, careful program branch and a saved input where they differ.
   Suggestion: KEEP. "Every lever names in DESIGN.md the oracle branch, the careful program branch and a saved input where they differ." Makes each lever checkable.
11. T11. Sources: F24 LEVER_RULES_v3.md:91; F27 LEVER_RULES_v3.md:115; F100 LEVER_RULES_v3.md:258; F111 20261101_route1_notes.md:13.
   Rule: never copy peer holes: doc against hidden data, underspecified graded field, unbounded unstated forms, source shape tests.
   Suggestion: KEEP. "Never copy holes: hidden data against a doc line, an underspecified graded field, unbounded unstated forms, source shape tests." Holes are QC defects, not levers.

BATCH 2. GRADING AND TESTS (10 items)
1. T12. Sources: F44 LEVER_RULES_v3.md:161; F108 20261101_route1_notes.md:10.
   Rule: every task states the exact bar sentence; tests compare whole documents per hidden run.
   Suggestion: KEEP. "Every task states the exact bar sentence; tests compare whole documents per hidden run." Still used by route 1 R0 point 3.
2. T13. Sources: F46 LEVER_RULES_v3.md:161.
   Rule: never grade a key, field or value form the shipped contract does not name.
   Suggestion: KEEP. "Never grade a key, field or value form the shipped contract does not name." Matches the CR7 deciding sentence rule.
3. T14. Sources: F55 LEVER_RULES_v3.md:170.
   Rule: the instruction states the exact command the tests run.
   Suggestion: KEEP. "The instruction states the exact command the tests use to run the program." An unstated cwd or flag is a defect, not a lever.
4. T15. Sources: F41 LEVER_RULES_v3.md:156; F195 _COMMON_RULES_v5.md:30.
   Rule: nothing visible shows the answer for a graded document; the oracle never contradicts the contract.
   Suggestion: KEEP. "Nothing in environment/ shows the answer for a graded document, and the oracle never contradicts the contract."
5. T16. Sources: F40 LEVER_RULES_v3.md:155; F66 LEVER_RULES_v3.md:181; F157 QC_FIX_PLAYBOOK_v3.md:49.
   Rule: the instruction states no rule of the computation, never echoes probe wording, never announces what the judge looks for.
   Suggestion: CHANGE. "Every criterion traces to an instruction sentence that asks for the output; that sentence never names the trap, the probe or the method." Reconciles these lines with RIF:11 (Q106).
6. T17. Sources: F36 LEVER_RULES_v3.md:151.
   Rule: a worked example only on invented toy values, at most one per rule, never a graded figure.
   Suggestion: CHANGE. "A worked example uses invented toy values, never a graded figure; when one is graded, the instruction asks for it (RIF:11)."
7. T18. Sources: F4 LEVER_RULES_v3.md:35.
   Rule: rules of engagement (scope, files that may change, tools, order, negatives) are always stated.
   Suggestion: KEEP. "Rules of engagement are always stated in a file the agent reads." Unstated scope is a QC finding.
8. T19. Sources: F28 LEVER_RULES_v3.md:116; F112 20261101_route1_notes.md:14.
   Rule: every instruction keeps the finish time sentence; no effort cap.
   Suggestion: KEEP. "Every instruction keeps the finish time sentence; no effort cap."
9. T20. Sources: F16 LEVER_RULES_v3.md:90; F213 _COMMON_RULES_v5.md:49; F124 20261101_route1_notes.md:40; F84 LEVER_RULES_v3.md:237; F299 state.json:28; F322 state.json:69.
   Rule: v3.7 design bars: first write tests at most 60, blinds at most 65, judge mid at most 20 (or 15 to 20), careful solver 0.10 to 0.20, DESIGN READY predicted final at most 35.
   Suggestion: CHANGE. "DESIGN READY needs a predicted final under the settings gate with the margin set in settings.json"; drop the other fixed bars, they predate the 85, 85, 40 gate.
10. T21. Sources: F356 state.json:108.
   Rule: READY FOR TRAJECTORY: QC 0 FAIL, oracle x3, STACKING pass, reflex program at most 0.20.
   Suggestion: DROP. the QC part is RIF:7, the reflex score is retired (QC_FIX_PLAYBOOK_v3.md:84), the oracle count is T46.

BATCH 3. QC FIXES (2 items)
1. T22. Sources: F136 QC_FIX_PLAYBOOK_v3.md:24.
   Rule: no fix softens a lever (the playbook soft directions) unless Ayush says so.
   Suggestion: CHANGE. "No fix softens a lever just to pass QC (the playbook's soft directions) unless Ayush says so for that finding. A real defect is always fixed: the shipped docs decide the value in one sentence and the hardness is rebuilt in a valid form (Q126)." Keeps hardening without protecting a defect.
2. T23. Sources: F400 issue.py:17; F401 issue.py:18.
   Rule: issue.py refuses a QC or harden session after a QC PASS.
   Suggestion: CHANGE. make both a logged warning like the round caps (Q120); RIF:7 still says stop at the first pass.

BATCH 4. RUNS AND PUSH (11 items)
1. T24. Sources: F93 LEVER_RULES_v3.md:242; F113 20261101_route1_notes.md:17; F230 _COMMON_RULES_v5.md:66; F238 pipeline_v4/PLAN.md:8.
   Rule: which pipeline order is current (3 blinds before QC, or route 1).
   Suggestion: CHANGE. "Order: design, build, full QC, 1 paid run, harden from what it got wrong, QC again, 1 paid run." Route 1 (1 Nov) is the newest; also covers the order part of F92.
2. T25. Sources: F17 LEVER_RULES_v3.md:90; F129 20261101_route1_notes.md:47.
   Rule: stop at DESIGN READY and wait for go; overnight the master may send go itself.
   Suggestion: CHANGE. "Stop at DESIGN READY and wait for Ayush's go"; drop the overnight self go, since a session stays issued until Ayush says running (R7). The F213 overnight part follows this item.
3. T26. Sources: F87 LEVER_RULES_v3.md:238.
   Rule: before diagnosing a run, diff its staged copy against the bundle.
   Suggestion: KEEP. "Before diagnosing a run, diff its staged copy against the bundle; a score from another tree is no baseline."
4. T27. Sources: F96 LEVER_RULES_v3.md:242; F232 _COMMON_RULES_v5.md:66; F242 pipeline_v4/PLAN.md:12; F268 pipeline_v4/PLAN.md:59; F273 pipeline_v4/PLAN.md:99; F296 KNOWLEDGE.md:119.
   Rule: a regrade is diagnostic only, with the judge only exception.
   Suggestion: KEEP. "A regrade is diagnostic only, except a judge only edit on a valid run with Ayush's written OK, repackaged by repackage_one.py."
5. T28. Sources: F99 LEVER_RULES_v3.md:245; F234 _COMMON_RULES_v5.md:68; F354 state.json:105.
   Rule: a run with a grader error is never a baseline.
   Suggestion: KEEP. "Only valid runs (no grader error) count as baselines."
6. T29. Sources: F233 _COMMON_RULES_v5.md:67; F265 pipeline_v4/PLAN.md:38.
   Rule: package from exactly the frozen bytes of the gate run.
   Suggestion: KEEP. "A pushed bundle is packaged from exactly the frozen bytes of the gate run, with that run's scores."
7. T30. Sources: F263 pipeline_v4/PLAN.md:38; F271 pipeline_v4/PLAN.md:66.
   Rule: QC Step 10 complete on the frozen bytes before push; a reduced auto sign off is owed.
   Suggestion: KEEP. "Before push, QC Step 10 (oracle, nop, stub, owner only) is complete on the frozen bytes."
8. T31. Sources: F297 KNOWLEDGE.md:120.
   Rule: every freeze records the tree sha; a gate run counts only on that sha.
   Suggestion: KEEP. "Every freeze records the tree sha; a gate run counts only on that sha." intake.py already checks it.
9. T32. Sources: F284 KNOWLEDGE.md:72; F323 state.json:70.
   Rule: only real runs measure hardness; a reviewer rating never gates.
   Suggestion: KEEP. "Only real runs measure hardness; a reviewer rating never gates."
10. T33. Sources: F314 state.json:60.
   Rule: 1 trajectory run per task while building; 8 runs only on final approval.
   Suggestion: CHANGE. move both numbers into settings.json as runs per task, like the Docker and session limits (Q122).
11. T34. Sources: F88 LEVER_RULES_v3.md:239; F114 20261101_route1_notes.md:17; F228 _COMMON_RULES_v5.md:65.
   Rule: no task is parked except on Ayush's word.
   Suggestion: KEEP. "No task is parked except on Ayush's word." Same line in three files.

BATCH 5. RECORDS AND PROCESS (4 items)
1. T35. Sources: F189 _COMMON_RULES_v5.md:24; F311 state.json:57; F390 README.md:62.
   Rule: never claim an unmeasured number; mark guesses UNVERIFIED; no secrets.
   Suggestion: KEEP. "Never claim a number you did not measure; mark guesses and unconfirmed values UNVERIFIED; no secrets in records." The IST part of F390 is covered by MASTER_RECOVERY.md Part A step 5.
2. T36. Sources: F360 state.json:114.
   Rule: write a checkpoint line before every compaction.
   Suggestion: DROP. the state card is rebuilt by the tools after every records write (R2), so it is the checkpoint.
3. T37. Sources: F325 state.json:72; F326 state.json:73.
   Rule: TRIAL FREEZE and TRIAL USE rules for the 21 to 24 Oct trial.
   Suggestion: DROP. the trial ended; mark the lines history.
4. T38. Sources: F307 state.json:53.
   Rule: all discussion work goes in the 20 Oct temp folder; ask before delete.
   Suggestion: DROP. stale; R3 and the tools now decide where records go. "Ask before delete" stays as how to text.

BATCH 6. REPOS AND SAFETY (2 items)
1. T39. Sources: F188 _COMMON_RULES_v5.md:23.
   Rule: never run generate_bundle.py --force, playground.py --model, or anything that uploads files or keys.
   Suggestion: KEEP. "Never run generate_bundle.py --force, playground.py --model, or anything that uploads files or keys." RIF:14 says read only but does not name these.
2. T40. Sources: F289 KNOWLEDGE.md:102; F290 KNOWLEDGE.md:104; F353 state.json:96.
   Rule: only Anubis_Tasks_Samples/Pass@1_New/ (Q57 scope Dinshi_Jain/Aditya Patel) holds current passing peers.
   Suggestion: CHANGE. "Mine passing peers only from the sources Ayush names as current" and Ayush names them now; anubis-stage-2 may have replaced Pass@1_New.

BATCH 7. CONFLICTS INSIDE OLD FILES (6 items)
1. T41. Sources: F71 LEVER_RULES_v3.md:204; F158 QC_FIX_PLAYBOOK_v3.md:50.
   Rule: exactly one code quality criterion: behavioural wording (J4) or one judgement wording (JD-18).
   Suggestion: CHANGE. use the JD-18 wording ("a Python reviewer would accept as maintainable") and keep "the oracle meets it"; it is the QC kit's own wording (Q125).
2. T42. Sources: F142 QC_FIX_PLAYBOOK_v3.md:34.
   Rule: what if figure criterion allowed (AL-2b, at most 6, weight at most 3) or banned (J1).
   Suggestion: CHANGE. allow it only when the instruction asks for that figure (RIF:11), with the AL-2b bounds; drop the J1 ban.
3. T43. Sources: F221 _COMMON_RULES_v5.md:58.
   Rule: a time limit at least 3x the oracle time, or reference at most 1/4 of the limit.
   Suggestion: CHANGE. one value, 4x (route 1 is newer), kept in settings.json.
4. T44. Sources: F22 LEVER_RULES_v3.md:91; F110 20261101_route1_notes.md:12.
   Rule: careful program keeping 60 percent = NO CORE; 0 differences over 2,000 variants = park.
   Suggestion: CHANGE. "0 differences over 2,000 variants: report to Ayush, never park on its own" (T34); the 60 percent NO CORE number waits for CR2.
5. T45. Sources: F79 LEVER_RULES_v3.md:229; F80 LEVER_RULES_v3.md:230; F91 LEVER_RULES_v3.md:241; F130 20261101_route1_notes.md:47; F253 pipeline_v4/PLAN.md:28; F227 _COMMON_RULES_v5.md:65; F81 LEVER_RULES_v3.md:236; F355 state.json:106; F358 state.json:111.
   Rule: 3 fresh blinds before QC or probe, 2 of 3 rule, a round counts at 10 percent loss, harden when the lower bound final is above 70, P13 blind under 100; route 1 needs none before QC.
   Suggestion: CHANGE. "Blinds before QC are not required on route 1; a blind is a diagnostic only"; drop the 70 and 100 thresholds (old gate). The Docker part of F358 is DECIDED by Q122.
6. T46. Sources: F246 pipeline_v4/PLAN.md:16; F301 state.json:30; F318 state.json:64.
   Rule: oracle 3 runs (state.json, ql procedure) against 2 oracle runs in auto mode.
   Suggestion: CHANGE. one oracle count in settings.json, default 3 per F333 (Ayush's x3); the auto mode reduced count is recorded as owed before push (T30).
