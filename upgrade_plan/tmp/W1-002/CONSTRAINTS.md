HARDENING CONSTRAINTS, ONE LIST (helper W1-002, 2 Nov 2026)

Scope: every rule that applies when a task is hardened, when a lever is designed, or when a hardened task is fixed for QC. Collected from the master chat records on branch claude/youthful-feynman-zug0uq. Each item gives the rule, its source as file:line, its status, and whether a script could check it.

SOURCE KEYS (all paths relative to the repo root)
1. RN = master_chat_tasks/prompts/issued/_adhoc/20261101_route1_notes.md (route 1 notes, R0 dated 2 Nov 2026, R1 to R6 dated 1 Nov 2026)
2. RN22 = master_chat_tasks/prompts/issued/_adhoc/20261022_round_notes.md (22 Oct; P9 v4 and P12 v5 still tell sessions to read sections C, E, F, G)
3. LR = master_chat_tasks/knowledge/LEVER_RULES_v3.md (v3.8, 2 Nov 2026)
4. KN = master_chat_tasks/knowledge/KNOWLEDGE.md
5. PB = master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md (v3, 27 Oct)
6. QR = master_chat_tasks/knowledge/QC_RULINGS.md
7. LL = master_chat_tasks/knowledge/LEAK_LIBRARY.md
8. FPD = master_chat_tasks/knowledge/FP_DOSSIER.md (header only, no rows yet)
9. PC = master_chat_tasks/knowledge/PROMPT_CHECKLIST.md
10. IX = master_chat_tasks/knowledge/INDEX.md
11. CR = master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md
12. P2 = master_chat_tasks/prompts/templates/P2_build_v5.md
13. P9 = master_chat_tasks/prompts/templates/P9_harden_from_results_v4.md
14. P11 = master_chat_tasks/prompts/templates/P11_full_qc_v3.md
15. P12 = master_chat_tasks/prompts/templates/P12_recheck_fix_v5.md
16. P13 = master_chat_tasks/prompts/templates/P13_blind_solve_v2.md
17. GO = master_chat_tasks/GOALS.md
18. RM = master_chat_tasks/README.md
19. ST = master_chat_tasks/state.json
20. AP = master_chat_tasks/auto/AUTO_POLICY.md
21. LJ = master_chat_tasks/lessons.jsonl (line number = JSON line)
22. FJ = master_chat_tasks/feedback.jsonl (line number = JSON line)
23. DJ = master_chat_tasks/decisions.jsonl (line number = JSON line; grepped, not read in full)
24. PL4 = master_chat_work/_dev_research/pipeline_v4/PLAN.md
25. WHY = master_chat_work/20261102_test_design_study/deep2/WHY.md
26. FP2 = master_chat_work/20261102_test_design_study/deep2/FIX_PLAN_v2.md (a proposal for master review, not adopted rule text)

STATUS WORDS
1. CURRENT: the newest text on this point and not overridden.
2. CURRENT, EXCEPTIONS: current, but Ayush granted one-task exceptions (named).
3. PARTLY SUPERSEDED: some of the text was overridden by a newer rule (named); the rest still applies.
4. SUPERSEDED: kept only to show what changed.
5. PROPOSED: written in a study or plan, not yet adopted into a rule file.

SCRIPT WORDS
1. yes: a script can decide it from the bundle, WORK files or run outputs.
2. partly: a script can find candidates or check that a record exists, a person must judge the rest.
3. no: needs reading or judgement.


SECTION 1. LEVER DESIGN AND LEVER ORDER

H1. Every task has at least one PRIMARY lever that carries at least 40% of positive test weight and that the careful exact program loses.
    Source: RN:5 (R0 1, 2 Nov 2026); LR:91 (1C v3.8 bullet); CR:49 (rule 17 prefix); RM:31; GO:18. Status: CURRENT. Script: partly; the weight share can be summed from the test weights and a lever map (WORK/LEVERS.md), "loses" needs the kill table run.

H2. The careful exact program is written from the shipped instruction, docs and data only, with no knowledge of the lever, reads every doc, uses an exact method and is self-checked against brute force on small inputs. It is the paid-run program when one exists, otherwise a fresh blind program.
    Source: RN:5. Status: CURRENT. Script: no.

H3. A lever-aware row (a reader written to handle the planted variant) is recorded in the kill table and is never a blocker.
    Source: RN:5; LR:91. Status: CURRENT. Script: no.

H4. Allowed primary kind (a): carrier or encoding variation inside a standard or format the docs name (other valid layouts of the same values, for example Word row wrappers, per-export codes and byte order written in that export's own docs).
    Source: RN:6; LR:91. Status: CURRENT. Script: partly; a script can grep the docs for the named standard and check the variant is value-preserving with an independent reader.

H5. Allowed primary kind (b): a documented branch that the shipped data never fires and the hidden data fires, at hidden size.
    Source: RN:7; LR:91; LR:150 (W5 BRANCH_FIRE). Status: CURRENT. Script: yes; instrument the oracle and count branch firings on shipped data (must be 0) and on each hidden seed.

H6. Allowed primary kind (c): measured scale. Hidden inputs stay inside the documented schema; the docs carry one stated runtime sentence with no method word; the reference runs at no more than 1/4 of the limit with both cores busy; the careful program needs at least 4x the limit on every lever corpus.
    Source: RN:8; LR:91. Status: CURRENT. Script: partly; timing is scriptable, "no method word" needs a word list plus reading.

H7. TIMEOUT and CRASH losses count toward a scale lever with no 30% cap.
    Source: RN:8 (Ayush 2 Nov 09:40 "yes i approve"); DJ:740. Status: CURRENT. Overrides LR:88 (v3.5 condition 3, 10 to 30%), DJ:593 (default 30%) and the one-task exceptions DJ:455 (tariff 60%), DJ:458 (schema), DJ:525 (outage 70%), DJ:544 (cold-chain 60%). Script: yes; kill table arithmetic.

H8. Shipped inputs, visible checks and doc examples stay fast (no warning to the agent); each lever corpus runs in its own call so a timeout never costs non-lever checks; a kept TS-11 warn gets a QC_DEFENCE row citing the approving decision.
    Source: RN:8; LR:88 (condition 1 and the own-call clause, older). Status: CURRENT. Script: partly; time the shipped run, read the tests for one call per corpus.

H9. Misread-rule held-out branches (L2 on a stated rule) are extras: stack them on top, never count them toward the 40% or toward R5 (a) and (b).
    Source: RN:9; LR:91 item (2). Status: CURRENT. Script: no.

H10. Every lever names, in DESIGN.md, the oracle branch (file:line), the careful or paid program's branch (file:line) and a saved input under WORK/ that makes them differ on a graded field. No named difference means no lever.
    Source: RN:11; FP2:33 (same idea, proposed). Status: CURRENT. Script: partly; check the three fields exist, then run the saved input through both programs and diff the graded field.

H11. Feasibility before build: prototype the core and the careful program and measure the lever in the Phase 1 kill table. If the careful program keeps at least 60% of the primary lever points, the verdict is NO CORE.
    Source: RN:12. Status: CURRENT (replaces RN:43 "recorded, NOT a blocker" for the primary lever). Script: yes, once both programs exist.

H12. A paid exact program with 0 determinate differences over at least 2,000 documented variants of the CURRENT bundle means park. This is a parking test, not hardness evidence.
    Source: RN:12; LJ:95; FP2:29 and FP2:37 (proposal source). Status: CURRENT, but see CONFLICTS C1 (parking only on Ayush's word). Script: yes; fuzz harness comparing oracle and paid program.

H13. Kill rows on a CHANGED bundle are design signal only; the paid run is the proof.
    Source: RN:12; LR:172 (G10, Ayush decision 11). Status: CURRENT. Script: no.

H14. Kill table rows: the paid-run program first, then first-write, all-but-one, every blind program on file and one careful enumerator; the loss kind (WRONG, TIMEOUT, CRASH) is written on every row.
    Source: RN:43 (R5 d). Status: CURRENT. Script: yes for the WRONG, TIMEOUT, CRASH split.

H15. The kill table always includes an exact solver that first splits the instance into independent parts and solves each part exactly, and the strongest plain exact solver (full search, DP, ILP style) under the stated limit (31 Oct outage lesson).
    Source: P9:67 (step 1b); P2:66. Status: CURRENT. Script: no.

H16. Solver, kill test and blind program runs go in Docker only (memory 4g, cpus 2, perl alarm wall cap, dockfree START=yes first); never on the host. Kill own child processes before reporting.
    Source: CR:48 (Always 16); P9:67; P2:66. Status: CURRENT. Script: yes; a wrapper can enforce it.

H17. When a rule sentence was added at fix time, patch the kill program to the current docs before reading its row.
    Source: LJ:91. Status: CURRENT. Script: no.

H18. An old blind program failing while the current paid program passes is not a hardening; blind-only losses never become a paid-run prediction.
    Source: LJ:97. Status: CURRENT. Script: no.

H19. When a lever targets a size cap, measure just under and just over the cap; read the caller of any cutoff or fallback before predicting the fallback.
    Source: LJ:106; LJ:96; LJ:98. Status: CURRENT. Script: partly.

H20. For Word carriers, fuzz with ECMA-376 row containers (sdt, customXml) and mc:AlternateContent early; paid programs read only direct w:tr children.
    Source: LJ:101; FP2:7; FP2:15. Status: CURRENT (task lesson, hangar and slipway). Script: partly.

H21. Carrier lever go numbers (proposal): an independent reader returns the same values on 300 of 300 variants, the paid program is wrong on at least 270 of 300, the oracle is exact on all; otherwise park the carrier change rather than broaden to unbounded markup.
    Source: FP2:11; FP2:17. Status: PROPOSED. Script: yes.

H22. A hidden rule may be absent from shipped examples, but its carrier, range and authority must be stated or determinate in agent-visible inputs; generated per-export docs vary values only within that bound and the oracle reads the generated docs too.
    Source: FP2:34. Status: PROPOSED (consistent with RN:21 and LR:29-37). Script: partly.

H23. A runtime lever claim keeps the agent's per-case exit code and seconds, measures the oracle on the slowest hidden case with a margin, and states the published size bound; a failed code==0 check does not prove a timeout.
    Source: FP2:35. Status: PROPOSED; the "state the size bound" part clashes with RN:20 and RN:37 (CONFLICTS C6). Script: partly.

H24. Hardening route: build, full QC, 1 paid run, harden from what that run (or a blind's program) actually got wrong, QC again, 1 paid run. A winning blind or paid program guides the harden and is never a reason to park. Nothing is parked except on Ayush's word.
    Source: RN:17; DJ:706 (1 Nov 11:27). Status: CURRENT. Script: no.

H25. Trajectory first: place levers from the paid trajectory read step by step: (1) files opened, order, never opened; (2) literals or branches fitted to shipped data (constants equal to shipped values, special cases keyed on shipped ids); (3) where it stopped checking; (4) every lost point by WRONG, TIMEOUT, CRASH and whether docs or reference were right, dispute rows fixed first. The new hidden check sits where (2) or (3) shows the agent did not look.
    Source: RN:24 to RN:30. Status: CURRENT. Script: partly; trajectory_readout.py gives the split, a grep of the agent program for shipped literals finds (2) candidates.

H26. Allowed lever forms R4: L2 held-out instances on a documented branch the paid program mishandles; LC1 bounded induction (finite family stated or shown, each instance's member fixed by its own data, hidden instances use members shipped data does not use). Rubric: probe band on checks the trajectory skipped; J3a kept; restatement criteria removed.
    Source: RN:33; RN:34; RN:36; LR:107 (LC1 legal only if the domain is stated and EVIDENCE_MAP lists it, one unlabelled witness max). Status: CURRENT as extras (R0 2 demotes misread-rule L2); see CONFLICTS C33 on LC1. Script: no.

H27. Never allowed: an unstated rule, a method word, a stated size bound, a trap announcement, an instructed effort cap, a judge-only band.
    Source: RN:37; LR:115; LR:116; LR:117. Status: CURRENT. Script: partly; grep for method words and effort cap phrases such as "stop at".

H28. Never copy: hidden data that contradicts a doc line, a graded field whose rule is underspecified, unbounded unstated forms, source-shape tests.
    Source: RN:13; LR:257 to LR:275 (holes list, section 8); WHY:39. Status: CURRENT. Script: partly; grep tests for source-shape checks (function length, import scans).

H29. Stated-rule levers (L1 to L11, S1, S3, S5, S6, H1 to H9, T1 to T4) are PAUSED: no new hardening round relies on them.
    Source: LR:86 (v3.3, 27 Oct). Status: CURRENT (reinforced by RN:9). Script: no.

H30. Design shape B (breadth) or D (degenerate shipped instance) plus a secondary source; Shape D: at most 3 sharp rules, each at least 25% alone, at least 70% of positive weight on hidden corpora.
    Source: LR:39 to LR:44; P2:38 to P2:40; P9:35. Status: PARTLY SUPERSEDED by LR:86 and RN:5 to RN:9 (see CONFLICTS C22). Script: partly.

H31. Lever status table: L2 held-out PROVEN default; L6 probe band PROVEN; unbounded induction, instructed effort caps, judge-only band and weight concentration are FALSE and never used.
    Source: LR:101; LR:102; LR:115 to LR:118. Status: PARTLY SUPERSEDED (L2 on a stated rule is now an extra, RN:9). Script: no.

H32. Rejected as sources: a cheap stateful rule with a silent redefinition, wrong-reading negatives, exact optimum with a stated method, odd carriers and format rules, mutation tiers alone.
    Source: LR:93. Status: PARTLY SUPERSEDED ("odd carriers" clashes with RN:6, CONFLICTS C2). Script: no.

H33. Plain decoys, look-alike files, encodings, DST, duplicate ids and superseded notes are noise only; a partial-authority decoy (S5) is a lever graded on both sides.
    Source: LR:133; P2:51. Status: PARTLY SUPERSEDED ("encodings" clashes with RN:6). Script: no.

H34. Hardness never from arithmetic, puzzles, formatting tricks, raw data volume, or hidden or ambiguous rules.
    Source: P2:52; KN:66. Status: CURRENT, except KN:66 also lists "resource pressure" as not working, which RN:8 contradicts (CONFLICTS C3). Script: no.

H35. Placement alone is not hardness; a self-testable rule is never a trap even when its separating cases are hidden.
    Source: LJ:8; LJ:76; LL:41. Status: CURRENT. Script: no.

H36. A lever set never repeats another live task's full set; exploration means several new levers per task, exactly one new lever is a logged exception.
    Source: LR:44; GO:16; DJ:28; DJ:29; P9:35. Status: CURRENT (older, not restated in R0). Script: partly; compare registry/levers.json sets.

H37. Prefer levers that interact (one feeds another); composition across files on hidden data is the working mechanism.
    Source: LR:143; LJ:14. Status: CURRENT (soft guidance). Script: no.


SECTION 2. HIDING AND LEAKS

H38. Every hidden check, held-out instance and lever stays in tests only; nothing in the docs announces it (no "note that", no trap list, no method word, no stated size bound).
    Source: RN:20 (R2). Status: CURRENT. Script: partly; grep for banned phrases, IN-17 judgement stays manual.

H39. Never explain a trap in any agent-visible file (W1, Never 8): no "not only X", "note that", "be careful", trap lists, rule counts, sentence naming the wrong reading, sentence announcing a property the shipped input establishes; no self-check paragraph in the instruction.
    Source: CR:27; LR:146; P2:120. Status: CURRENT. Script: partly; precheck greps the fixed phrases.

H40. No author notes in agent-visible files (TRAP, trap list, lever, inverse, decoy, grader, hidden test, answer key), including comments, file names and data fields.
    Source: CR:28; LJ:79; KN:99. Status: CURRENT. Script: yes; precheck author-note grep.

H41. No answer for any graded document in environment/ (no answer key, golden or sample output, solved list, expected figure, claimed total, even one that agrees with the contract). Exceptions: one unlabelled L11 witness per lever, one toy worked example per rule.
    Source: CR:30 (Never 11); LR:156 (W11); LJ:7; LJ:15. Status: CURRENT. Script: partly; compare environment files and numbers against oracle outputs.

H42. A worked example uses invented toy values that appear in no shipped or hidden file, at most one per rule, never says which case is the trap.
    Source: LR:151 (W6). Status: CURRENT. Script: partly; search shipped and hidden data for the toy values.

H43. Shipped controls are real and honest and reconcile under both the right and the wrong reading of every lever.
    Source: LR:152 (W7); CR:30. Status: CURRENT. Script: partly; run each wrong-reading variant and check the control.

H44. Separating cases live in hidden inputs only (except L5); WORK/BRANCH_FIRE.md shows each hard branch with shipped count 0 and firing on every hidden corpus that grades it.
    Source: LR:150 (W5); P2:62. Status: CURRENT. Script: yes.

H45. Write each rule in the file that governs its data, in plain forms; numbered procedures leak; a decoy is never refuted beside its use.
    Source: LR:147; LR:148; LL:23; LL:37; LL:8. Status: CURRENT as writing guidance (as a hardness source it is paused, H29). Script: no.

H46. One rule register; instruction.md states the job, output paths, whole-document exactness, rerun promise and rules of engagement, and no rule of the computation.
    Source: LR:155 (W10); P2:50. Status: CURRENT. Script: partly.

H47. When the generator re-renders rule documents per hidden corpus, the sentences stay word for word except the values, and the register lists which values change.
    Source: LR:157 (W12). Status: CURRENT. Script: yes; diff rendered documents with values masked.

H48. Blind prompts (P11 QC and P13 blind solve) contain no lever names, notes paths, scores or trap words; the blind copy holds only instruction.md and environment/.
    Source: PC:30; P13:7; P13:8. Status: CURRENT. Script: yes.

H49. No answer recoverable from data: neutral ids, no meaningful prefixes (for example cap-/rej-).
    Source: PB:51 (DS-4); QR:136. Status: CURRENT. Script: partly.

H50. No slug or author string inside SHA-pinned test text.
    Source: LR:169 (G8); P2:96. Status: CURRENT. Script: yes.

H51. Never echo probe wording in instruction.md.
    Source: LR:181; P2:111. Status: CURRENT. Script: yes; string overlap between judge.toml and instruction.md.

H52. Never state how many rules or defects exist, never name the files holding them, never list trap topics.
    Source: LJ:38; LJ:44. Status: CURRENT. Script: partly.

H53. A withheld parameter shared by visible and hidden data is a shortcut; hidden inputs keep shipped reference tables but reseed the segment files, because agents bake shipped tables into code.
    Source: LJ:23; LR:250. Status: CURRENT. Script: partly.

H54. A harden removes every giveaway found in diagnosis, including every IN-17 announcement sentence, any self-check paragraph and any "other scales" wording.
    Source: P9:58. Status: CURRENT. Script: partly.

H55. Every leaked lever gets a LEAK_LIBRARY row; build and harden sessions read LEAK_LIBRARY before designing and never repeat a row.
    Source: P9:53; P2:27; LL:3. Status: CURRENT. Script: no.


SECTION 3. INSTRUCTION WORDING

H56. Every task states the exact bar, for example "Each output document is graded whole, and only an exact match counts"; tests compare whole documents per hidden run; the CL-4 defence quotes Final_checklist.md:491.
    Source: RN:10 (R0 3); LR:161 (G1); LR:166 (G5). Status: CURRENT. Script: yes; grep instruction.md for the sentence.

H57. The instruction states the rerun promise (the program runs again on fresh inputs of the same layout), gives no list of axes that change, never says "at other scales" or "other sizes", never names a branch as tricky.
    Source: LR:166; CR:27; P2:119; QR:145 (QL Q4). Status: CURRENT. Script: partly.

H58. The instruction keeps "Leave enough of that time to finish and write your final reply." and carries no effort cap.
    Source: RN:14 (R0 7). Status: CURRENT. Script: yes.

H59. Include "You have N seconds to complete this task." with N equal to [agent] timeout_sec, and keep the online-lookup sentence.
    Source: P2:121. Status: CURRENT. Script: yes; compare with task.toml.

H60. Never mention tests, a grader, a checker, a verifier, a judge, weights or "reward"; the instruction stays under 6000 characters.
    Source: P2:122. Status: CURRENT (see CONFLICTS C30 on "graded"). Script: yes.

H61. State the exact command (interpreter, flags, cwd, arguments) the tests use; tests run exactly that; no unstated python -I and no unstated cwd.
    Source: LR:170 (G8a); P2:96; P2:119; LR:225. Status: CURRENT. Script: yes; compare instruction.md with the run helper in tests.

H62. Rules of engagement (scope, files that may change, tools, process order, every negative) are always stated in a file the agent can read.
    Source: CR:25 (Never 6); LR:35. Status: CURRENT. Script: partly.

H63. One reading for everything graded (IN-16). A deliverable-property rule is stated or settled by one determinate shipped fact that contradicts every wrong reading, listed in WORK/EVIDENCE_MAP.md; silence never settles anything; "QC deferred" is never a pass.
    Source: CR:25; LR:29 to LR:36; RN:21; LR:243. Status: CURRENT. Script: partly; check EVIDENCE_MAP rows exist for every rule with no sentence.

H64. A degenerate shipped instance always needs the rule sentence for every branch it hides: the instance may hide the case, never the rule.
    Source: LR:33. Status: CURRENT. Script: no.

H65. Where several documents carry rules, one instruction sentence names which document wins.
    Source: LR:153 (W8); P2:119. Status: CURRENT (P2 says "where useful"). Script: no.

H66. Every key, field and value form any test reads is named somewhere in the shipped contract (minimal explanation is fine); never grade a key the agent cannot read.
    Source: LR:161 (QL 26 Oct Q3); QR:144. Status: CURRENT. Script: partly; extract keys from tests and grep environment/.

H67. A time or memory limit is at least 3x the oracle's measured time on the hidden inputs, or there is no limit.
    Source: CR:58. Status: PARTLY SUPERSEDED by RN:8 and RN:44 (reference at most 1/4 of the limit, so at least 4x, with both cores busy). Script: yes.

H68. Time the oracle on worst in-limit inputs before stating any performance limit.
    Source: LJ:75; DJ:484; DJ:493 (schema oracle broke its 10 s promise, DS-20). Status: CURRENT. Script: yes.

H69. Never state a size or runtime limit that hands over the exact method.
    Source: P2:52; LR:23; LR:80. Status: CURRENT (matches "no method word" in RN:8). Script: no.

H70. A fix never adds a hint, example, explanation, rule count, or moves a rule next to its use or into instruction.md (soft directions).
    Source: PB:24; P12:58. Status: CURRENT. Script: partly; diff the fix against the previous copy.

H71. Doc changes are allowed when they open a new documented separating case (for example flood harden r4 added one documented rule).
    Source: DJ:721; DJ:745 (doc changes allowed 2 Nov); DJ:740 item 4. Status: CURRENT. Script: no.


SECTION 4. TESTS AND WEIGHTS

H72. Whole-document exact grading per hidden corpus with exactness stated; report the one-fact-wrong score anyway; every amplified slip traces to a stated single-reading rule, never to an ambiguity, unstated rule or oracle defect.
    Source: LR:161 (G1). Status: CURRENT. Script: partly.

H73. At most one stated cross-corpus gate per task, with its sentence in instruction.md; CL-4, TS-19 and AL-28 must pass.
    Source: LR:161. Status: CURRENT. Script: partly.

H74. Per-row ownership: each output row or byte is owned by exactly one test, shared columns masked elsewhere; a test that compared nothing never passes.
    Source: LR:162 (G1a). Status: CURRENT. Script: partly.

H75. One property per test (TS-13); no test returns early on another document's scalar; whole-document asserts report the first differing record.
    Source: LR:163 (G2); P2:136. Status: CURRENT. Script: partly; precheck flags checks opening 2 or more output files.

H76. No two tests read the same observable with the same logic (TS-26); count observables, not check names; a common core prerequisite is paid once.
    Source: LR:160; FP2:36; WHY:26. Status: CURRENT. Script: partly.

H77. No positive check passes on an absence (TS-25); a "writes only into X" check must be a negative.
    Source: P2:105; LJ:93; PB:45. Status: CURRENT. Script: yes; vacuity probe with the unedited shipped tool.

H78. Hidden share: Shape D at least 70% of positive weight on generated hidden corpora; every shape at least one hidden rerun per output family; shares measured through the call graph, never by test names.
    Source: LR:164 (G3). Status: CURRENT (shape framing partly superseded, H30). Script: partly; stacking_check.py gives hints that must be corrected by hand (LJ:61).

H79. Negatives grade only cheating acts, grouped by act, at most 5 per act across tests and judge (AL-28); no negative grades a lever; no wrong-reading detector; each quotes its stated sentence in QC_DEFENCE; none depends on the exit code alone.
    Source: LR:165 (G4); P2:104. Status: CURRENT. Script: partly.

H80. Every negative's trigger list matches a stated sentence word for word; overlapping negatives stand down on acts another negative prices.
    Source: QR:156; LJ:85; PB:37. Status: CURRENT. Script: partly.

H81. At least 2 mutation tests, each counted only on corpora where the plain hidden run of the same family is exact.
    Source: LR:167 (G6). Status: CURRENT. Script: partly.

H82. Assertion messages carry the first differing path, recorded in ctrf.
    Source: LR:168 (G7). Status: CURRENT. Script: yes.

H83. An embedded seeded generator in tests/ builds hidden inputs (seed only in tests/); the agent program reruns as a foreign uid from a foreign cwd; hidden seeds change every named release literal; rare fixtures use their own RNG stream.
    Source: LR:169 (G8); P2:96. Status: CURRENT. Script: partly.

H84. Expected values are independent of the oracle: check_exact.py recomputes from visible documents only; an override-removal probe proves the oracle reads each footnote or erratum; never hard-code shipped expected values from the oracle alone.
    Source: LR:171 (G9); P2:93. Status: CURRENT. Script: partly.

H85. Cost table: inject each wrong reading alone; Shape D every lever alone at least 25%; every all-but-one row predicted final under 70.
    Source: LR:172 (G10); P2:100. Status: PARTLY SUPERSEDED (primary lever 40% in RN:5; final 35 in RN:40). Script: yes.

H86. Rule coverage: one mutant per AL-2 unit and per ordering, precedence or tie-break the shipped input establishes; every row fails at least 1 test; tie-breaks need a planted tie; precheck fails a 0 row.
    Source: LR:173 (G11); PB:36; P2:101. Status: CURRENT. Script: yes.

H87. The generator asserts every drawn value is inside the stated bounds on every seed, plants every branch of each multi-branch rule on some seed, and with the reference survives 300 seeds; no shared mutable cache across tests.
    Source: LR:174 (G12); QR:59; QR:157; P2:102. Status: CURRENT. Script: yes.

H88. Weights only 1, 3 or 5 (kit W2 refuses 2): 5 core, 3 sub-goal, 1 existence only; core never 1 (TS-20); never lower an existing core outcome check while adding lever checks.
    Source: P2:103; LR:176; LJ:94; LJ:102; LJ:108; KN:9. Status: CURRENT. Script: yes.

H89. At least 10 tests and 8 criteria; no upper cap; above 35 tests the TS-23 warn is recorded with the count, never merged away.
    Source: CR:63; PB:41; PB:71; DJ:112; DJ:336 (3). Status: CURRENT. Script: yes.

H90. Never raise points because the run failed a check, never lower them because the model passed; add a test only for a rule the docs already state, on hidden data from the same generator, one observable; never fit a check to one run's quirk.
    Source: KN:111 to KN:117; PL4:39; PL4:49 to PL4:55. Status: CURRENT. Script: no.

H91. After a data edit: regenerate the _SHIPPED_DATA embedding, recompute reward.toml (0.5/P per channel), rewrite TRUTH.md sha256 values by script as the last edit.
    Source: CR:38 (Always 6). Status: CURRENT. Script: yes; precheck recomputes.

H92. A fix may not remove a check or hidden input that lost points in the last run's loss table.
    Source: P12:32; P12:68. Status: CURRENT. Script: partly.

H93. Stage-2 self-checks before QC: TS-13 multi-file scan, CL-2 vacuity probe, TS-16 negatives silent on the oracle and on 2 honest variants, promise table (every instruction sentence graded), literal table (every literal stated or derivable), judge type and target table.
    Source: P2:134 to P2:141; PL4:20 to PL4:27. Status: CURRENT. Script: yes for most rows.

H94. Write the wrong implementation for each lever and confirm it loses that lever's points; a check no wrong implementation fails is worthless.
    Source: P2:99. Status: CURRENT. Script: yes.

H95. Run variance: treat a single test score as plus or minus 20 points and a single final as plus or minus 10; same bytes spread about 17.5 tests and 20 final.
    Source: LR:175 (G13); LR:242. Status: CURRENT. Script: no.

H96. A verifier timeout kills the whole process group; a weight-1 stdlib-only positive runs the engine on earned output, never an import scan.
    Source: DJ:708; LJ:99. Status: CURRENT. Script: partly.

H97. Avoid scoring cliffs where one field costs a whole family unless the instruction states exactness; report the first differing field.
    Source: WHY:34; WHY:39; FP2:36. Status: CURRENT (study evidence). Script: partly.

H98. Before deleting a negative, grep validate_bundle.py for required names (s7.4 requires negative_hardcoded_sample_answers); retarget it to behaviour evidence instead.
    Source: LJ:110; DJ:762. Status: CURRENT. Script: yes.


SECTION 5. JUDGE RUBRIC

H99. No figure criterion of any kind (output figure, final-reply figure, what-if figure); a figure enters the judge only inside the honesty negative J3b.
    Source: LR:180 (J1); CR:53. Status: CURRENT (see CONFLICTS C8). Script: yes; lint for number words in criteria.

H100. Probe band: 8 to 16 probe criteria, each w3, importance important, type process, evaluation_target trajectory, together 55 to 70% of positive judge weight, each from templates P-a to P-h, each naming the requirement it serves.
    Source: LR:181 (J2); LR:182 to LR:190; CR:56. Status: CURRENT, EXCEPTIONS (hangar accepted with no judge probes, DJ:762). Script: yes; count and share.

H101. The oracle shows every criterion: solve.sh's self-check stage prints "check <id> ok" plus one witness line; a criterion with no oracle-shows row in WORK/JUDGE_MAP.md is removed (JD-7).
    Source: LR:181; LR:212; QR:142; CR:56. Status: CURRENT. Script: partly.

H102. Probe guards J2b: no negative on a file the agent hand-created in out/ when the program is the deliverable; no "session" confinement clause; one act per criterion; no literal-value negative over scratch code; no process criterion re-charging a tested trap; no "establishes intermediate V"; no self-consistency negative; no menu of acts.
    Source: LR:191 to LR:199. Status: CURRENT. Script: no.

H103. Honesty negatives in every judge: J3a claim of a passing check or byte-identical output with no run after the last edit (w -3, disjoint from every other negative); J3b figure differs from the delivered file (w -5); J3c overstated check size (w -3) when relevant.
    Source: LR:200 to LR:203; CR:54; DJ:336 (7). Status: CURRENT. Script: yes; precheck flags a missing J3a, J3b.

H104. Write negative exclusions with "other than", never "not" (judge_qc J10).
    Source: LR:200. Status: CURRENT. Script: yes.

H105. Exactly one behavioural code-quality criterion when the deliverable is code (every exception handler acts on the error it catches; a missing or malformed declared input stops the run with a message naming the file), met by the oracle line by line.
    Source: LR:204 (J4); CR:54; P2:111. Status: CURRENT (wording clashes with PB:50, CONFLICTS C9). Script: partly.

H106. No criterion endorses a reading the tests penalise; [judge] mode = "batched".
    Source: LR:205 (J5). Status: CURRENT. Script: yes for mode.

H107. One per-item enumeration criterion on the final answer (J6); a deterministic artifact behaviour is a test, never a criterion (J7); no criterion restates a method a test grades (J8); no criterion overlaps a test (JD-8).
    Source: LR:206 to LR:208; RN:36. Status: CURRENT. Script: partly.

H108. Stated process rules get one instruction-following criterion each, quoting the sentence (order w3, work directory w -1), at most 2.
    Source: LR:210 (J10). Status: CURRENT. Script: partly.

H109. Annotations hold exactly mode, type, evaluation_target, importance; criterion ids are renumbered sequentially R1, R2 after drops; the five-key header stays exact.
    Source: LR:212; PB:56; LJ:103; P2:114. Status: CURRENT. Script: yes.

H110. The grader-read negative is anchored to paths starting with /tests/ at the filesystem root or /logs/verifier; files under /app are never this act.
    Source: CR:57; LJ:74. Status: CURRENT. Script: yes.

H111. Judge target: predicted probe mid at most 20 (probes counted at the peer pass rate 25%).
    Source: LR:90 (v3.7); CR:49. Status: CURRENT (older target LR:179 differs, CONFLICTS C10). Script: partly; arithmetic from JUDGE_MAP.

H112. Criteria use positive grammar starting "The agent" or "The response", counts instead of "some", one verb clause each (JD-5); absence-shaped positives are not allowed.
    Source: P2:113; P2:141; QR:158. Status: CURRENT. Script: partly.

H113. A judge-only rebuild never rescues a tests-100 task; at least one positive test must be lost.
    Source: LR:237; QR:147 (QL Q5); DJ:265. Status: CURRENT. Script: yes.


SECTION 6. QC KIT RULES AND THE FIX PROCESS

H114. QC result target: zero fails; any minor or warn left must be genuine and as few as possible (supersedes the dec 101 zero-warn rule). The brief to this helper says "zero findings".
    Source: CR:64; KN:39; DJ:112. Status: CURRENT, but GO:34 and ST:32 still say zero findings including warns (CONFLICTS C11). Script: yes for counting.

H115. Read QC rules from the live kit files, matching each check on ID and wording.
    Source: CR:36 (Always 4); P11:37. Status: CURRENT. Script: partly.

H116. WORK/QC_DEFENCE.md has a row for every new or changed check before QC: rule ids (at least IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, AL-2, AL-27, CL-2, CL-3; P9 adds AL-1, CL-4), why it passes, safe fallback (playbook row id plus its DO fix written out).
    Source: RN:22; P9:62; P2:67. Status: CURRENT. Script: partly; check one row per changed check id.

H117. WORK/EVIDENCE_MAP.md lists every convention shown only by shipped evidence, with file:line of the source and the competing readings it rules out.
    Source: RN:21; LR:36. Status: CURRENT. Script: partly.

H118. WORK/RULE_TRACE.md: a generator branch with no sentence row is a hidden rule; delete the branch or write the sentence.
    Source: LR:37. Status: CURRENT. Script: partly.

H119. Fix directions use the playbook DO column only, never the NEVER column; one line per finding in the section 2 format; any lever marked easier carries a compensation; a REBUT quotes the kit line.
    Source: PB:23; PB:24; PB:74; PB:75; P12:9; P12:58. Status: CURRENT. Script: partly.

H120. Guard rules G1 to G7 bind every fix: never paste QC's "Fix:" text; never move an assert into an existing check or weight onto a conduct criterion; never delete a clause without naming what grades the rest; re-check every touched item; vacuity probe again; docs and TRUTH regenerated last by script; byte diff before any generator regeneration.
    Source: PB:62 to PB:70; FJ:20. Status: CURRENT. Script: partly; G6 and G7 yes.

H121. Trap survival: after the fixes every lever keeps at least 90% of its before loss and no separating hidden case is removed; else compensate in the same lever family, at most 2 tries, then PAUSED.
    Source: PB:81 to PB:86; PB:88; P12:68. Status: CURRENT. Script: yes.

H122. Noise check: a finding on lines unchanged since a passing round is KEPT with the diff as evidence and an FP_DOSSIER row.
    Source: CR:45 (Always 13); PB:58; RM:38 (U13). Status: CURRENT. Script: yes.

H123. Every FIX re-checks the ids FIX_SIDE_EFFECTS lists for it; every new or split test gets NEW-CHECK hygiene (TS-13, TS-25, TS-14, TS-16, TS-26).
    Source: CR:44; CR:46; PB:57. Status: CURRENT. Script: partly.

H124. No KEEP or FIX ruling without the kit line and the side-effect row.
    Source: RM:35 (U4). Status: CURRENT. Script: partly.

H125. Fix receipt: tree sha before and after, changed check ids with old and new weights, oracle, owner and nop before and after, the saved agent program re-scored before and after, and a rescan of AL-18, DS-22, DS-27, JD-14, AL-28, AL-1, AL-2, AL-27.
    Source: P12:70. Status: CURRENT. Script: yes for most items.

H126. QC rounds 2 and later run in recheck mode with carry-over (previous report, KEPT.md, CHANGED_LINES).
    Source: PL4:9; QR:150; P11:29 to P11:33. Status: PARTLY SUPERSEDED: LJ:107 says run full mode after any harden that touches tests/ or judge; RN:47 says the master issues a full QC after build and gates (CONFLICTS C16). Script: no.

H127. Route 1: when QC reports fails, the master reports them and Ayush decides the next step each time.
    Source: DJ:709. Status: CURRENT (manual mode; AP:27 auto mode issues one fix session). Script: no.

H128. A "suggestion" finding (add a hint, example, count, move a rule closer) is KEPT only with verifiable evidence; a KEEP resting on a lever never held; otherwise state the rule once neutrally in its governing file.
    Source: PB:53; P12:55. Status: CURRENT. Script: no.

H129. IN-17 needs both parts named (the discovery and the input that establishes it); either missing is a REBUT; exempt: rules of engagement, CL-6 signposts, IN-16 settlers, DS-25 literals.
    Source: PB:31; QR:31. Status: CURRENT. Script: no.

H130. CL-5: a silent requirement passes if stated, established by an example the agent is actually given, or compared insensitively (FC:492).
    Source: QR:41. Status: CURRENT. Script: no.

H131. Harden prompts state the disposition of known pre-existing validator FAILs up front.
    Source: LJ:109. Status: CURRENT. Script: no.

H132. Bundle text: no em or en dashes, no TODO, FIXME, XXX, PLACEHOLDER, no {{X}}, __X__ or <TAG> markers, LF endings, files under 100 MB, ENV HOME first in environment/Dockerfile, litellm==1.105.0 pinned; paths a Dockerfile RUN creates under /app/data ship as files.
    Source: CR:39 (Always 7). Status: CURRENT. Script: yes.

H133. Mandatory format: chown root and chmod 755 /logs/verifier; tests/Dockerfile pip line exactly harbor-rewardkit==0.2.1 litellm==1.105.0; _grant_read before setpriv (H6, TS-30).
    Source: P9:61; ST:77 (rules[25]); KN:83; KN:90. Status: CURRENT. Script: yes.

H134. No __pycache__ or .pyc in a bundle; run Python under bundles with PYTHONDONTWRITEBYTECODE=1.
    Source: CR:47 (Always 15). Status: CURRENT. Script: yes.

H135. xref_check.py prints 0 findings; PRECHECK CLEAN before DONE; STACKING_CHECK written every build, harden and fix round before P11.
    Source: P9:63; P12:42; CR:42; LR:215 to LR:226. Status: CURRENT. Script: yes (stacking partly).

H136. List each QC check changed in the kit since the QL base commit as PASS or FIXED.
    Source: P9:69; P11:70 to P11:72. Status: CURRENT. Script: yes.

H137. Hidden generators stay inside every stated bound and produce every promised case; a test is never stricter than the contract.
    Source: QR:59; QR:62; QR:157; PB:44. Status: CURRENT. Script: yes via generator asserts.

H138. Every stated or input-established rule (order, precedence, tie-break, qualifier) is triggered by a graded input (AL-27); fix by adding hidden reseeded rows inside bounds, never by deleting the rule.
    Source: PB:36; QR:131. Status: CURRENT. Script: yes via RULE_COVERAGE.

H139. Every instruction promise is graded (AL-2); remove ungraded requests such as final-reply figures.
    Source: PB:33; QR:133. Status: CURRENT. Script: partly via the promise table.

H140. TRUTH.md matches what shipped (DS-22, AL-18), recomputed by script after the last tests/ edit; TRUTH has 8 sections with real focal, drift and trap markers.
    Source: PB:35; PB:47; P2:125 to P2:127. Status: CURRENT. Script: yes.

H141. The oracle never breaks the written contract; fix the oracle, never the contract (DS-20).
    Source: PB:48; CR:30. Status: CURRENT. Script: partly.


SECTION 7. ORACLE, NOP AND RUNTIME

H142. Gates after any change to tests/, solution/, environment/ or data: oracle x3 = 1.000 (the kit asks x5; x5 only in a FINAL QC round), owner-only x1 = 1.000, nop x1 = 0.000, stub and forgery reported, copies built by the live kit's exe_copy.py.
    Source: P9:70; P12:69; P11:90; PC:37; ST:80 (rules[28]). Status: CURRENT (count is muddled, CONFLICTS C18). Script: yes.

H143. Stub: a stub near a genuine partial score, or any content check that paid, is a finding; forgery target 0.05 or less (22 Oct); playground D3 stub 0.25 or less (WARN).
    Source: P11:98; RN22:41; KN:27. Status: CURRENT but vague (CONFLICTS C19). Script: yes.

H144. Auto-mode QC Step 10 is reduced to oracle x2 and nop x1; oracle 3 to 5, stub and owner-only are owed before push.
    Source: P11:103; AP:25; PL4:38. Status: CURRENT. Script: yes.

H145. The oracle is deterministic, offline, runs as uid 1000, is written from the contract not from test code, shares well under 20% of lines with test_output.py, and solve.py has 30 or more substantive lines.
    Source: P2:91; P2:92. Status: CURRENT. Script: partly.

H146. Any test that runs agent code under a dropped uid makes the program and its temp inputs readable first, and kills leftovers by uid as well as process group; checks that drop to the same uid are serialised.
    Source: RN22:31 to RN22:34; RN22:55; LJ:34; LJ:47. Status: CURRENT. Script: partly.

H147. Reference at most 1/4 of any stated limit with both cores busy; verifier worst case at most 90% of the verifier limit; shipped inputs fast; oracle and owner 1.0, nop 0.
    Source: RN:44 (R5 e); DJ:496 (3600 s timeout, worst 3240 s). Status: CURRENT. Script: yes.

H148. Warm the verifier image before any harbor run (900 s start limit).
    Source: RN22:72; P12:69; P11:89. Status: CURRENT. Script: yes.

H149. Docker gate runs: bundle lock, timestamp with seconds plus random hex, no --delete, no prune, three lanes after the warm build, each lane started only on dockfree START=yes; run folders under _runs/, not /tmp.
    Source: P11:76 to P11:91; P12:69; PC:36. Status: CURRENT (older RN22:67 and RN22:70 differ, CONFLICTS C17). Script: yes.

H150. No DONE while any own Docker job runs or any placeholder remains in a report.
    Source: LJ:105. Status: CURRENT. Script: yes.

H151. Leave the agent a realistic path to finish inside its timeout (agent timeout means no trajectory and no reward); measure a reference agent's wall time; a task limit must not invite open-ended load testing.
    Source: RN:14; LJ:42; DJ:715 (flood a3 agent timeout 7200 s, no score). Status: CURRENT. Script: partly.


SECTION 8. DATA AND SCALE

H152. Volume: at least 20,000 lines total and at least 2,000 per csv, tsv, jsonl, txt or log file; volume is not the difficulty; every file matters to a graded result.
    Source: P2:85; P2:86; KN:27. Status: CURRENT (build rule; also binds a harden that adds files). Script: yes.

H153. Hidden inputs stay inside the documented schema; the hidden generator never produces an open (ungraded, two-reading) case.
    Source: RN:8; QR:27; PB:30. Status: CURRENT. Script: yes via asserts.

H154. A fix never shrinks or simplifies hidden data and never moves a separating row into shipped data (except L5).
    Source: PB:24. Status: CURRENT. Script: partly.

H155. Never regenerate tests or data from a generator without a byte diff; never run a stale build script.
    Source: CR:43 (Always 11); PB:70; RN22:48. Status: CURRENT. Script: yes.

H156. Data story plausible and consistent in shipped and hidden data (DS-6).
    Source: PB:52. Status: CURRENT. Script: no.

H157. Hidden data for a branch lever fires at hidden size, from the same generator as shipped data.
    Source: RN:7; KN:114. Status: CURRENT. Script: yes.


SECTION 9. PROCESS AND CAPS

H158. Pipeline order: design, build with precheck self-checks, 3 fresh blind reads, one full QC with fix-all, QC recheck rounds, freeze, 1 harness run.
    Source: CR:66; PL4:8; GO:38; RM:31. Status: PARTLY SUPERSEDED on route 1 (RN:47: no fresh blinds required before QC; RN:17 route), CONFLICTS C4.

H159. No hardening after a QC PASS; any later change goes only through the master's trajectory read-out, a QC recheck and 1 new run.
    Source: CR:29 (Never 10); RM:37 (U12); PL4:8. Status: CURRENT. Script: partly via issue.py refusal.

H160. P9 runs only when a run on frozen QC-passed bytes missed the gate (or Ayush asks); Phase A first: diff staged tests and ctrf ids against the bundle; an ARTEFACT score stops the round.
    Source: P9:3; P9:10; P9:43. Status: CURRENT. Script: partly.

H161. Diagnosis answers the 4 causes (run error, harness change, our rounds made it easier, levers weak by design) with evidence and names the primary cause.
    Source: P9:44 to P9:49. Status: CURRENT. Script: no.

H162. Stop at DIAGNOSIS READY or DESIGN READY (or NO CORE with the measured table) and wait for "go".
    Source: P9:54; RN:47; P2:69. Status: CURRENT. Script: no.

H163. Round limit: stop after 3 harden rounds (ROUND LIMIT); drop after 3 rebuild or harden rounds.
    Source: P9:14; P9:76; ST:90. Status: PARTLY SUPERSEDED by LR:239 (no auto-park) and frequent Ayush overrides (CONFLICTS C14). Script: yes via issue.py.

H164. issue.py refuses past 2 fix rounds per QC, 2 QC rounds, harden after PASS, drop rule at 3 rounds, 8-session time box, unless --override with Ayush's verbatim words.
    Source: RM:19; P12:11. Status: CURRENT. Script: yes.

H165. Sessions edit only BUNDLE, WORK and OUT; no git writes; never edit the kit, harness or master records.
    Source: CR:19 to CR:21; P9:29. Status: CURRENT. Script: yes.

H166. Every report ends with "Lessons for the master", at most 5 lines.
    Source: CR:71. Status: CURRENT. Script: yes.

H167. Every claim quotes file:line, a trajectory step or command output; inferred items are marked INFERRED; unmeasured means "did not run"; scores are labelled tests-only unless a judged run happened.
    Source: PC:40 to PC:42; CR:24; CR:61. Status: CURRENT. Script: partly.

H168. Not evidence: differential fuzz of an old program on a changed bundle; a per-lever claim from one run; oracle-injection numbers as agent behaviour; a blind's self-marked judge PASS without the step it cites.
    Source: LR:244; P9:52. Status: CURRENT (tension with RN:40, CONFLICTS C7). Script: no.

H169. Worker prompts for GPT or opencode say: no subagents, all work in the main chat.
    Source: FJ:32; DJ:595. Status: CURRENT. Script: yes (prompt lint).

H170. Outside auto mode paid runs are started by Ayush; auto mode caps paid runs at 6 per day unless the plan says otherwise.
    Source: FJ:24; AP:52; DJ:470. Status: CURRENT (DJ:593 allows the master to start one after QC PASS and freeze, CONFLICTS C28). Script: yes in auto.py.


SECTION 10. GATE AND SCORING

H171. Final gate: tests < 85 AND rubric < 85 AND final < 40 on 1 valid run of the frozen QC-passed bytes; final = (tests + rubric) / 2.
    Source: CR:62; LR:237; AP:28; ST:126. Status: CURRENT, EXCEPTIONS (warrant final < 50, DJ:504, DJ:506; metered pushed at 44.05, DJ:514; tariff a6 47.84 pushed, DJ:504). Script: yes.

H172. Push needs 1 valid run on the frozen bytes (tree sha recorded at freeze); any change after the run voids it; the package is built from exactly those bytes.
    Source: LR:237; CR:67; KN:120; FJ:19 (older, 2 runs). Status: CURRENT, EXCEPTIONS (paid run during or before QC, DJ:734, DJ:756). Script: yes; tree sha compare.

H173. A missed gate is never re-run on the same bytes; the trajectory read-out comes first.
    Source: LR:242; PL4:13; AP:29. Status: CURRENT. Script: yes.

H174. Regrade is diagnostic only, except when the edit touches judge files only, the run was valid, Ayush wrote OK, and the run is repackaged with repackage_one.py.
    Source: LR:242; PL4:12. Status: CURRENT. Script: partly.

H175. DESIGN READY on route 1: (a) the paid-run program on the new tests gives predicted final = (tests + judge mid) / 2 of at most 35; (b) lever share at least 40%; (c) EVIDENCE_MAP and QC_DEFENCE complete; (d) the kill table; (e) timing per H147.
    Source: RN:39 to RN:44. Status: CURRENT, EXCEPTIONS (flood accepted at predicted mid 38.2, DJ:761; hangar at 41.4, DJ:762). Script: yes for (a), (b).

H176. v3.7 DESIGN READY items (c) no blind program above tests 65 and (e) every generic solver and blind loses at least 15% of lever points by WRONG.
    Source: LR:90; CR:49. Status: SUPERSEDED on route 1 by RN:39 (R5 replaces 1C v3.7 (c) and (e)) and by RN:5 to RN:12.

H177. After a missed gate: tests >= 85 means a new test lever; tests < 85 but rubric >= 85 or final >= 40 means a judge probe band (mid <= 20) and penalties, plus more test lever if the rubric alone cannot reach final < 40.
    Source: KN:118; PL4:56; LR:237. Status: CURRENT. Script: yes.

H178. Only valid:true lines in registry/scores.jsonl count; a run with a grader error is never a baseline; diff the staged copy and ctrf ids before diagnosing.
    Source: LR:238; LR:245; CR:68. Status: CURRENT. Script: yes.

H179. Read check values from verifier/reward-details.json (report.json "passed" on negatives is unreliable); trajectory_readout.py can mislabel timeouts as WRONG, so check by reading.
    Source: P9:42; KN:108; DJ:647. Status: CURRENT. Script: partly.

H180. Blind judge estimate: lower bound (PASS only, probes only when the CHECKS log shows the act, minus fired negatives), upper bound (PASS plus UNSURE), mid (probes at 25%).
    Source: LR:231 to LR:236; P13:33. Status: CURRENT. Script: yes.

H181. A blind round counts only when fresh blind programs lose at least 10% of positive test weight; harden or redesign before a probe when the lower-bound final is above 70 on 2 of 3 blinds.
    Source: LR:236; LR:241; CR:65; P9:78; P2:156. Status: PARTLY SUPERSEDED (route 1 needs no fresh blinds, RN:47; the 70 threshold predates the final < 40 gate). Script: yes.

H182. Old target numbers (careful-solver tests 0.10 to 0.20; per-run gate tests < 100, rubric < 100, overall < 70; tests < 90 rubric < 90 overall < 30).
    Source: ST:28; ST:31; ST:89; RM:31 (end of line); DJ:63; DJ:23. Status: SUPERSEDED by H171.


COUNTS PER THEME
1. Lever design and lever order: H1 to H37 = 37
2. Hiding and leaks: H38 to H55 = 18
3. Instruction wording: H56 to H71 = 16
4. Tests and weights: H72 to H98 = 27
5. Judge rubric: H99 to H113 = 15
6. QC kit rules and fix process: H114 to H141 = 28
7. Oracle, nop and runtime: H142 to H151 = 10
8. Data and scale: H152 to H157 = 6
9. Process and caps: H158 to H170 = 13
10. Gate and scoring: H171 to H182 = 12
Total: 182 (of which SUPERSEDED 2, PROPOSED 3, the rest CURRENT or PARTLY SUPERSEDED)
