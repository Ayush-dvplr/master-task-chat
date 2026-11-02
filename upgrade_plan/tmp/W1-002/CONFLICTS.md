CONFLICTS, OVERRIDES AND VAGUE RULES (helper W1-002, 2 Nov 2026)

Source keys are the same as in CONSTRAINTS.md (RN, RN22, LR, KN, PB, QR, LL, PC, IX, CR, P2, P9, P11, P12, P13, GO, RM, ST, AP, LJ, FJ, DJ, PL4, WHY, FP2). Each entry gives: what disagrees, both sources, which side is newer, and a severity (HIGH means a hardening session could follow the wrong rule today; MEDIUM means it causes doubt or rework; LOW means stale text or a one-task exception).

SECTION A. DIRECT CONFLICTS IN CURRENT TEXT

C1. Parking after a feasibility test versus "nobody parks but Ayush".
    Side 1: RN:12 (R0 5, 2 Nov): a paid exact program with 0 determinate differences over at least 2,000 documented variants "= park"; LJ:95 repeats "0 diffs in >=2000 = park"; FP2:37 says "stop route-1 hardening. Park".
    Side 2: RN:17 (R1, 1 Nov): "Nothing is parked except on Ayush's word"; LR:239 (v3.2, 26 Oct): NO AUTO-PARK, parked only on Ayush's word; AP:29 "Never park".
    Newer: R0 (2 Nov) but it sits in the same file as R1 and does not say whether "park" means "propose park to Ayush". Severity: HIGH.

C2. Carrier and encoding variation as the PRIMARY lever versus older text that rejects carriers and encodings.
    Side 1: RN:6 and LR:91 (v3.8, 2 Nov): primary kind (a) is carrier or encoding variation inside a named standard or format.
    Side 2: LR:93 "Rejected as sources ... odd carriers and format rules"; LR:133 "encodings ... are noise only"; P2:51 "encodings and duplicate ids are noise only"; LL:29 V0-7 "format rules are not levers".
    Newer: v3.8 overrides "where they differ" (LR:91), but LR:93, LR:133 and P2:51 were not edited or marked, so a session reading P2 top to bottom gets the old rule. Severity: HIGH.

C3. Timeout and crash losses: count with no cap (new) versus 10 to 30% cap or not at all (old text still in the bodies of the templates).
    Side 1: RN:8 and DJ:740 (2 Nov): TIMEOUT/CRASH counts with no 30% cap.
    Side 2: LR:87 (v3.4 Law-1, timeouts do not count); LR:88 (v3.5, cost 10 to 30%); CR:49 body (after the v3.8 prefix it still says 10 to 30%); P9:67 body ("counts only under v3.5 ... 10-30% ... otherwise add a WRONG stage or report PILOT_WEAK"); P2:66 body; KN:108 (section T step 1, "cost 10-30%"); GO:18 text; PL4:11, PL4:19, PL4:28; ST:33 (kill_rule "WRONG output (Law 1)"); DJ:593 (31 Oct, "default timeout share 30%"); DJ:470 ("crash/timeout <=30%"); KN:66 ("Does not work ... resource pressure").
    Newer: R0. Only a bracket prefix marks the override in CR:49, P9:67 (pointer) and GO:18; the full old rule follows each prefix. Severity: HIGH.

C4. Fresh blind reads required versus not required.
    Side 1: RN:47 (R6, 1 Nov): "no fresh blinds are required before QC on route 1".
    Side 2: CR:66, PL4:8, GO:38, RM:31 (order includes 3 fresh blind reads); P9:78 and P2:156 (next step: master issues 3 fresh P13 blind reads, round counts only with at least 10% loss); LR:241 (v3.3: "the fresh blind read ... is the only measure of a round").
    Newer: R6, but P9 v4 (the harden template) was not updated, so its closing step still orders blinds. Severity: HIGH.

C5. The careful exact program can be "a fresh blind program", but the blind template forbids careful work.
    Side 1: RN:5: CAREFUL EXACT PROGRAM is the paid-run program, "else a fresh blind program", and it is "self-checked against brute force on small inputs".
    Side 2: P13:31 and P13:32: the blind writes its program once, self-checks on shipped data only, fixes a crash once, then freezes: "do not build extra test inputs, do not polish". That is a reflex program, not a careful one.
    Newer: R0, but no P13 v3 exists. A NO CORE verdict (H11) measured with a P13 blind understates what a careful program keeps. Severity: HIGH.

C6. May a size or runtime bound be stated?
    Side 1: RN:20 and RN:37: no stated size bound; LR:166 (G5): no "at other scales" or "other sizes" wording; P2:52: never state a size or runtime limit that hands over the method.
    Side 2: RN:8 (R0 1c): one stated runtime sentence is required for a scale lever; LR:174 (G12) and QR:59: hidden values stay inside "the bounds the contract states"; QR:66 (dispatch): "AVOID: state run caps"; FP2:35 (proposed): "state the published size bound"; WHY:35: "Hard scale ceilings matter when published".
    Newer: R0 for the runtime sentence; nothing settles whether a size bound (rows, nodes) may be stated, while TS-19 needs some bound for the generator to stay inside. Severity: HIGH.

C7. Is running an old agent program on a changed bundle evidence?
    Side 1: LR:172 (G10, Ayush decision 11): "Differential fuzz of an EARLIER agent program against a CHANGED bundle is not evidence of anything"; LR:244; P9:52.
    Side 2: RN:40 (R5 a): DESIGN READY rests on "the paid-run program, run in Docker on the new tests"; RN:25 to RN:30 (trajectory first); FP2:9 and FP2:11 use the a3 program on a changed bundle.
    Partial fix: RN:12 says such rows are "design signal only, the paid run is the proof". Still, R5 (a) makes this signal a hard bar. Severity: MEDIUM.

C8. Figure criteria in the judge.
    Side 1: LR:180 (J1) and CR:53: no figure criterion of any kind, what-if or not; QR:139 AVOID counterfactual figure criteria.
    Side 2: LR:108 (1D, 29 Oct): "LC3 counterfactual what-if figures in judge (J11) PROMISING ... 4-8 what-ifs"; PB:34 (AL-2b row): "keep it as a what-if figure criterion per LEVER_RULES J1 (... max 6, w <= 3 each)"; P2:6 (v3 history: "J1 <= 6 what-if figures").
    Newer: LR 1D is dated after J1's v3 text, but J1 is the rule section and 1D is a status table. No J11 exists in section 4. Severity: MEDIUM.

C9. Wording of the one code-quality criterion.
    Side 1: LR:204 (J4) and CR:54: behavioural ("every exception handler acts on the error it catches ...; a missing or malformed declared input stops the run with a message naming the file").
    Side 2: PB:50 (JD-18 row): "a Python reviewer would accept as maintainable, judged on its names, function structure and error handling"; QR:108: "AVOID vague code-quality criteria; use a named shape (J4)".
    Newer: both are v3 (26 to 27 Oct); the playbook row quotes an older J4. Severity: MEDIUM.

C10. Judge target level.
    Side 1: LR:90 (v3.7) and CR:49: predicted probe mid at most 20.
    Side 2: LR:179: "the judge half lands near 25-45%"; LR:211 band arithmetic expects 30 to 37%; LR:89 (v3.6, superseded) mid 15 to 20.
    Also: LR:181 makes the probe band mandatory, but DJ:762 (2 Nov 23:28) accepted hangar with "no judge probes".
    Newer: v3.7 for the number; LR:179 and LR:211 were never updated. Severity: MEDIUM.

C11. "Zero findings" versus "zero fails with genuine minimum minors or warns".
    Side 1: GO:34 ("pass the kit QC with zero findings (dec 101)"); ST:32 (acceptance: "zero QC findings (fail, minor, warn)"); ST:29 (caps tests <= 35, "zero findings incl. warns"); the brief for this helper says "zero findings".
    Side 2: CR:64, KN:39, DJ:112 (24 Oct 12:50, "supersedes dec 101 zero-warn"); CR:63 and PB:41 (a TS-23 warn above 35 checks is kept on purpose); AP:26 (minors accepted as PL notes); DJ:569, DJ:579, DJ:642 (warns accepted and frozen).
    Newer: DJ:112 (24 Oct). GOALS.md still states the older rule, and any task with more than 35 checks cannot have zero findings. Severity: MEDIUM to HIGH (it changes when a harden is finished).

C12. Stale gate numbers still present in live files.
    Current: final gate tests < 85 AND rubric < 85 AND final < 40 (CR:62, LR:237, AP:28, ST:126).
    Stale: RM:31 ("gate met (tests<100, rubric<100, overall<70) = push"); ST:31 (targets.test_phase_gate tests<100); ST:89 (rules[37]); ST:28 and ST:69 (careful-solver tests 0.10 to 0.20); FJ:19 (tests<100 and final<70 on 2 runs); LR:236 and CR:65 (harden when lower-bound final above 70); LR:172 and P2:100 (all-but-one final < 70).
    One-task exceptions: warrant final < 50 (DJ:504, DJ:506); metered pushed at 44.05 (DJ:514); tariff a6 47.84 pushed (DJ:504).
    Severity: MEDIUM (README is in the compaction read order).

C13. DESIGN READY bar versus accepted designs.
    Side 1: RN:40 (R5 a): predicted final at most 35.
    Side 2: DJ:761 (flood accepted at predicted mid 38.2) and DJ:762 (hangar accepted at 41.4, no judge probes).
    These are recorded Ayush exceptions, not rule changes. Severity: LOW, but it shows the bar is soft in practice.

C14. Round limits versus no auto-park.
    Side 1: P9:14 ("Harden round [[ROUND]] of 3") and P9:76 ("Stop after 3 harden rounds ... ROUND LIMIT"); ST:90 (DROP RULE, permanent, after 3 rounds); RM:19 (issue.py drop rule at 3 edit rounds).
    Side 2: LR:239 (v3.2): no auto-park, issued "with Ayush's override past the 3-round limit"; RN:17: nothing parked except on Ayush's word; AP:30 (auto mode gives its own override); DJ:378 (5 harden rounds already on district).
    Severity: MEDIUM.

C15. QC fix round caps.
    Side 1: RM:19 (issue.py: 2 fix rounds per QC, 2 QC rounds); P12:6 (at most 2 P12 rounds per QC); P11:5 (max 3 rounds).
    Side 2: DJ:662 (lever hunt plan: "QC max 3 fix rounds"); repeated overrides DJ:711, DJ:723, DJ:728.
    Severity: LOW.

C16. Recheck mode or full mode for the QC after a harden.
    Side 1: PL4:9 (decision 2): round 2 and later in recheck mode with carry-over; QR:150; P12:78 (next step is a P11 recheck).
    Side 2: LJ:107 (2 Nov 22:38): "Recheck-mode QC inherits blind spots; run full mode after any harden that touches tests/judge"; RN:47: "the master issues a full QC"; RN:17 "QC again".
    Newer: LJ:107, but no template was changed (it is a lesson only). Severity: MEDIUM.

C17. Docker concurrency rules.
    Side 1: RN22:67 (max 2 Docker-heavy jobs) and RN22:70 (runs strictly one after another in ONE chain, never a second chain). P9:25 and P12:24 still tell every session to read RN22 sections C, E, F, G.
    Side 2: P11:89 to P11:91 and P12:69 (31 Oct): three parallel lanes after a warm build, each gated by dockfree START=yes; AP:47 (31 Oct) "replaces the 27 Oct 'at most 2 Docker-heavy' advice".
    Newer: 31 Oct lanes. Severity: LOW.

C18. Oracle run count.
    KN:38 (official Step 10: oracle 5 times); P11:90 (default x3, x5 only in a FINAL round); P2:132 and P9:70 (x3); ST:80 (internal build gates stay x2); DJ:45 (Q28, oracle x2 + nop x1); AP:25 (auto QC: x2); DJ:470 (oracle x3 only when tests/ changed); DJ:601 (keep 3).
    Vague for a harden: x3 is the working rule, but when x5 must happen before push is not tied to any step on route 1. Severity: LOW.

C19. Stub and forgery thresholds.
    KN:27 (playground D3: stub 0.25 or less, WARN); RN22:41 (forgery target 0.05 or less); P11:98 (judged as a share of P against the CL-2 forgery price, no number).
    Severity: LOW (vague).

C20. Runtime margin for any stated limit.
    Side 1: CR:58: limit at least 3x the oracle's measured time.
    Side 2: RN:8 and RN:44: reference at most 1/4 of the limit with both cores busy (at least 4x); FP2:17: oracle at most 15 s for a 60 s cap.
    Newer: R0 and R5. CR:58 was not updated. Severity: LOW to MEDIUM.

C21. Lever cost thresholds.
    Side 1: RN:5 (primary at least 40%); RN:41 (lever share at least 40%).
    Side 2: LR:172 and P2:100 (Shape D every lever alone at least 25%); LR:41 (Shape B 15 rules at least 3% each); LR:89 (v3.6, 25 to 40%, superseded); LJ:20 (21 Oct: cap each lever's share at 25% or less).
    Newer: R0. P2's Phase 4 gate still prints the old numbers. Severity: MEDIUM.

C22. Shapes and stated-rule sources still asked for by the templates.
    Side 1: LR:86 (stated-rule levers PAUSED); RN:9 (misread-rule branches are extras only).
    Side 2: P2:38 to P2:40 and P9:35 ask the master to fill SHAPE (B or D) and HARDNESS SOURCES with S1 or S2 primary; P2:51 "Each stated rule's wrong reading is an Opus habit"; LR:101 (L2 held-out "PROVEN, default test lever").
    Severity: MEDIUM.

C23. Where hardness should live.
    Side 1: ST:62 (rules[10], 20 Oct): "hardness must live mainly in the INSTRUCTION/task itself ..., not only in tests and rubric".
    Side 2: RN:20 (R2): "Every hidden check, held-out instance and lever stays in tests only".
    Newer: RN. state.json is in the compaction read order. Severity: LOW.

C24. Genuineness intent.
    Side 1: GO:18 ("Difficulty comes from computation on hidden data, never from withheld rules"); LR:25 and LR:60 (silence forbidden); CR:25 (Never 6).
    Side 2: DJ:595 (31 Oct: "'bypass' = levers other taskers use without QC alerts"); DJ:651 and DJ:706 ("we are not making 100% genuine tasks ... built so that it passes the QC").
    Reading: the newer words do not allow hidden rules; they ask for QC-passing levers. But WHY:39 shows 52% of teammate losses came from QC FAIL patterns, so "do what others do" can pull toward forbidden holes. Severity: MEDIUM (intent is vague).

C25. How much of a carrier must be written down.
    Side 1: FP2:7 (slipway proposal) adds one instruction.md sentence and one doc paragraph naming w:sdtContent, w:customXml and mc:AlternateContent.
    Side 2: RN:20 (nothing in the docs announces a lever); LR:155 (W10: instruction states no rule of the computation); CR:27 (no sentence announcing a property); FP2:15 (hangar: "No new instruction or doc text is needed" because the doc already names ECMA-376); FP2:34 (carrier, range and authority must be stated or determinate).
    Open question: is naming the standard enough (hangar) or must the variant forms be listed (slipway)? Listing them looks like a trap announcement; not listing them may fail IN-16 or TS-19. Severity: HIGH (it decides whether lever kind (a) passes QC without leaking).

C26. A warning sentence that exists in a shipped bundle.
    Side 1: WHY:25 reports slipway instruction.md:17-19 "explicitly warns that shipped data misses quiet documented branches".
    Side 2: CR:27 (Never 8) and LR:146 (W1): no sentence announcing a property or branch; IN-17.
    This is a rule-versus-practice gap; the slipway bundle was not opened by this helper. Severity: LOW to MEDIUM.

C27. PROMPT_CHECKLIST stale gates.
    Side 1: PC:45 requires "reflex gate <= 0.20"; PC:28 points to QC_FIX_PLAYBOOK.md (v1).
    Side 2: PB:84 ("The reflex score part is retired 24 Oct"); P9:7 ("reflex gate replaced"); IX lists QC_FIX_PLAYBOOK_v3 as active.
    Severity: LOW (but the checklist is applied to every prompt).

C28. Who may start a paid run outside auto mode.
    Side 1: FJ:24 (29 Oct): "Outside auto mode, never start paid harness runs; ask Ayush"; DJ:470 (29 Oct).
    Side 2: DJ:593 (31 Oct): "master may start paid run outside auto after QC PASS+freeze within cap (effective at switch-on)".
    Newer: DJ:593, but "effective at switch-on" is unclear and README has no matching line. Severity: LOW.

C29. Rule ids pointing at LEVER_RULES_v1.
    PB:3 ("Read with LEVER_RULES_v1.md (W/G/J rules)"); LL:3 ("Rule ids (W*, G*, J*) refer to knowledge/LEVER_RULES_v1.md"). The active file is LEVER_RULES_v3.md, and ids changed meaning between versions (for example the v1 era allowed up to 6 what-if figure criteria under J1, P2:6). A fix row that says "W3" or "J1" may mean the old rule. Severity: MEDIUM.

C30. "Graded" in the exact-bar sentence versus the ban on naming the grader.
    Side 1: RN:10 and LR:166 require "Each output document is graded whole ...".
    Side 2: P2:122: never mention tests, a grader, a checker, a verifier, a judge, weights or "reward".
    Reading: "graded" is not in the list and the kit explicitly accepts the exactness sentence (FC:491), so this is vague, not a real clash. Severity: LOW.

C31. Template version in state.json.
    ST:49 says P12 is v4; IX:16 says P12 v5 is ACTIVE and v4 SUPERSEDED; RM:31 also names "P12 v4". Severity: LOW.

C32. Number of runs before push.
    FJ:19 (27 Oct 11:20): 2 valid harness runs of the exact updated bundle before push.
    LR:237 (v3.4, Ayush 27 Oct 17:17) and CR:67: 1 valid run on frozen bytes.
    Newer: 1 run. Severity: LOW.

C33. LC1 bounded induction: primary, extra, or pilot?
    RN:34 (R4) allows LC1; LR:107 (1D) says PROMISING, second pilot; LR:58 (L11) says the evidence-induction pilot failed 3 of 3; RN:5 to RN:9 list three primary kinds and do not mention LC1, and LC1 is not a "misread rule", so R0 2 does not classify it either. Severity: MEDIUM (vague).

C34. Paid run before or during QC.
    Side 1: CR:66 and PL4:8 (QC, freeze, then 1 run); RN:17.
    Side 2: DJ:734 (flood paid a4 before QC v4) and DJ:756 (slipway a5 run in parallel with QC v4, counts only if QC passes with no byte change).
    These are one-task Ayush exceptions. Severity: LOW.

C35. Shipped-only (visible) weight share.
    QR:66 ("shipped-only checks stay <= 5% (G3)"); LJ:10 (visible weight 0.10 of P or less); LR:164 (G3: Shape B no floor, Shape D at least 70% hidden). G3 itself no longer says 5%. Severity: LOW.

C36. Three names for nearly the same program.
    RN:5 "careful exact program" (a blocker for the primary lever via RN:12); RN:43 "one careful enumerator" (recorded, not a blocker, except for the primary lever per the 2 Nov bracket); RN:5 "lever-aware row" (never a blocker). The difference between a careful enumerator and a careful exact program, and who writes each, is not defined. Severity: MEDIUM.

C37. When P9 is used.
    P9:3 ("used only when a run on frozen QC-passed bytes missed the gate with tests 100 (new test lever) or when Ayush asks").
    RN:17 and KN:118: harden after any missed gate, and for tests below 85 the next step can be a judge band. Severity: LOW.


SECTION B. VAGUE TERMS THAT A SCRIPT OR A SESSION CANNOT APPLY AS WRITTEN

C38. "method word" (RN:8, RN:20, RN:37): no list exists. A session cannot lint it.
C39. "both cores busy" (RN:8, RN:44): the measuring set-up (what loads the second core, which container size) is not given.
C40. "documented variants" and "determinate difference" (RN:12): which generator, which mutators, and what counts as determinate are not defined; FP2:29 counts "generator plus targeted cases".
C41. "at hidden size" (RN:7) and "measured scale" (RN:8): no relation between shipped size and hidden size is stated, and C6 leaves open whether any size may be written down.
C42. "careful program >= 4x the limit on every lever corpus" (RN:8): it does not say whether a program that the agent could easily make faster (a method change) still counts; LR:91 last sentence says the v3.4 "agent recovers" claim did not hold, which is evidence, not a rule.
C43. "dispute rows are fixed first" (RN:29): no rule says who rules on a dispute between docs and reference, or whether a fix to the reference needs a new QC.
C44. "Every task carries the sentence" (RN:10) versus G1/G5 "provided instruction.md states" (LR:161): the exact wording is an example ("for example") in LR:166 but a quoted sentence in RN:10; whether a field-level variant (DJ:746 "instruction exact bar already at :32 (field level), kept") satisfies R0 3 is open.


TOP 5 BY SEVERITY
1. C3 (old timeout rules still in template bodies).
2. C5 (the careful exact program cannot be produced by the P13 blind template).
3. C25 together with C6 (how much of a carrier or size bound may be written without leaking).
4. C1 (who may park).
5. C2 together with C22 (P2 and LEVER_RULES still call carriers and encodings noise, and still ask for stated-rule shapes).

COUNT
Section A: 37 conflicts or overrides (C1 to C37). Section B: 7 vague terms (C38 to C44). Total 44.
