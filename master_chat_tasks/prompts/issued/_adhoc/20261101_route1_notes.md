# Route 1 notes (Ayush 1 Nov 2026 11:00 IST; R0 added 2 Nov 2026 "proceed"). Every route-1 prompt cites this file; it overrides LEVER_RULES_v3 where they differ. R0 overrides R4 and R5 below where they differ. Pre-R0 bytes: master_chat_work/_snapshots/20261102_v3.8_pre/.

## R0. Lever order (2 Nov 2026; same text as LEVER_RULES_v3 1C v3.8 bullet; decisions.jsonl 09:17-13:08)
Why: since 31 Oct every paid run on a "documented rule the agent may misread" lever scored tests 100 (depot a1/a2, hangar a1 137/137, flood a4). The programs were right (depot a2 0/2312 WRONG offline, hangar a1 0/5904); nothing leaked; QC removed no lever. Opus 5 reads every doc, writes an exact method and checks it against its own brute force. Teammate study 1deab9c (`master_chat_work/20261102_test_design_study/deep2/WHY.md`): their large test losses come from parsers fitted to the shipped carrier (fabbe645, 1d61e794, 5048c412), branches the shipped data never fires at hidden scale (a710b00e, 18b5d99f), and amplification under a stated exact bar; one of ten from a misread rule.
1. Primary lever, at least one per task, carrying >= 40% of positive test weight, that the CAREFUL EXACT PROGRAM loses (every doc read, exact method, self-checked against brute force on small inputs). CAREFUL EXACT PROGRAM = written from the shipped instruction, docs and data only, with no knowledge of the lever (the paid-run program when one exists, else a fresh blind program); a lever-aware row (a reader written to handle the planted variant) is recorded in the kill table, never a blocker. Allowed kinds:
   (a) carrier or encoding variation inside a standard or format the docs name (other valid layouts of the same values; hangar Word row wrappers, fabbe645 per-export codes and byte order written into that export's own docs);
   (b) a documented branch the shipped data never fires and the hidden data fires, at hidden size (a710b00e unsealed components, 18b5d99f sparse cards);
   (c) measured scale: hidden inputs inside the documented schema, one stated runtime sentence (no method word), reference <= 1/4 of the limit with both cores busy, the careful program >= 4x the limit on every lever corpus (so a slow or fast grader gives the same result). TIMEOUT/CRASH counts with no 30% cap (Ayush 2 Nov 09:40 "yes i approve"); shipped inputs, visible checks and doc examples stay fast; each lever corpus in its own call; kept TS-11 warn gets a QC_DEFENCE row citing that decision.
2. Misread-rule held-out branches (L2 on a stated rule) are EXTRAS: stack them on top, never count them toward the 40% or toward R5 (a)/(b). Evidence: slipway a4 lost 60 to one (crosswalk) while depot, hangar and flood lost 0.
3. Amplify with the existing G1/G5 (LEVER_RULES section 3): instruction.md states the exact bar ("Each output document is graded whole, and only an exact match counts"), tests compare whole documents per hidden run; CL-4 defence quotes Final_checklist.md:491. Every task carries the sentence.
4. Every lever names, in DESIGN.md: the oracle branch (file:line), the careful or paid program's branch (file:line), and a saved input under WORK/ that makes them differ on a graded field. No named difference = no lever.
5. Feasibility before build: prototype the core plus the careful program and measure 1 (a)/(b)/(c) in the Phase 1 kill table. Careful program keeps >= 60% of primary lever points = NO CORE (this replaces R5 (d) "recorded, NOT a blocker" for the primary lever; extras may still be kept). A paid exact program with 0 determinate differences over >= 2,000 documented variants of the CURRENT bundle = park (this is a parking test, not hardness evidence; kill rows on a CHANGED bundle stay design signal only, the paid run is the proof, LEVER_RULES G10).
6. Never copy: hidden data that contradicts a doc line (59417607 clocks vs record_dictionary.md:19), a graded field whose rule is underspecified (80202e15 fx_rate null), unbounded unstated forms (8defd7be, 05550e00), source-shape tests (5048c412 function length).
7. Instruction keeps "Leave enough of that time to finish and write your final reply." (flood a3: agent timeout = no trajectory = no reward). No effort cap.

## R1. The route
Build -> full QC -> 1 paid harness run -> harden from what that run (or a blind's program) actually got wrong -> QC again -> 1 paid run. Schema and warrant were hardened this way. A blind or paid program that wins is the guide for the harden, never a reason to park. Nothing is parked except on Ayush's word.

## R2. Built to pass QC, levers stay hidden
- Every hidden check, held-out instance and lever stays in tests only. Nothing in the docs announces it (IN-17: no "note that", no trap list, no method word, no stated size bound).
- Every graded fact has a determinate source in the shipped docs or shipped data (IN-15, IN-16, DS-21, LEVER_RULES section 0b). A convention may be shown only by shipped evidence (rows, an example file, a worked figure) as long as exactly one reading fits that evidence. List each one in `WORK/EVIDENCE_MAP.md` with file:line of the source and the competing readings it rules out.
- Write `WORK/QC_DEFENCE.md` rows for every new or changed check: rule ids (at least IN-15, IN-16, IN-17, DS-21, TS-19, TS-23, TS-26, JD-5, JD-8, AL-2, AL-27, CL-2, CL-3), why it passes, safe fallback.

## R3. Trajectory first
Lever placement comes from the paid trajectory (and the blind programs), read step by step:
1. Which files the agent opened, in what order, and which it never opened.
2. Literals or branches in its program fitted to the shipped data (grep the program for constants equal to shipped values, special cases keyed on shipped ids, a reading chosen because it matched shipped output).
3. Where it stopped checking: no re-run on altered data, no independent recompute, claims without a run.
4. Every lost point by kind: WRONG / TIMEOUT / CRASH, and whether the docs or the reference was right (dispute rows are fixed first).
The new hidden check sits where (2) or (3) shows the agent did not look.

## R4. Allowed lever forms
- L2 held-out instances that fire a documented branch the paid program mishandles.
- LC1 bounded induction (the warrant pattern): a finite family stated or shown, each instance's member fixed by its own data; hidden instances use members the shipped data does not use. A program that hard-codes the shipped fit gets WRONG.
- Hidden-scale TIMEOUT only where Ayush granted a time-out exception for that task (flood: yes, 31 Oct 11:45). [SUPERSEDED 2 Nov by R0 1(c): hidden-scale TIMEOUT allowed on every task under the R0 gap conditions.]
- Rubric: probe band (J2, P-a..P-h) on checks the trajectory skipped; J3a honesty negative kept; restatement criteria that tests already grade are removed (JD-8).
Not allowed: an unstated rule, a method word, a stated size bound, a trap announcement, an instructed effort cap, a judge-only band.

## R5. DESIGN READY bar (route 1; replaces LEVER_RULES 1C v3.7 (c) and (e) for these rounds)
(a) the paid-run program, run in Docker on the new tests, loses enough positive test weight that predicted final = (its new tests + predicted judge mid) / 2 <= 35;
(b) lever share >= 40% of positive test weight;
(c) EVIDENCE_MAP and QC_DEFENCE complete per R2;
(d) [2 Nov: for the PRIMARY lever R0 5 makes the careful program a blocker; the 'recorded, NOT a blocker' wording below holds only for extras] kill table: paid-run program first, then first-write, all-but-one, every blind program on file, one careful enumerator. Loss kind on every row. A careful enumerator that keeps the lever is recorded, NOT a blocker (the paid run is the gate);
(e) reference <= 1/4 of any stated limit with both cores busy; verifier worst case <= 90% of the verifier limit; shipped inputs fast; oracle/owner 1.0, nop 0.

## R6. Hand-off
Stop at DESIGN READY (or NO CORE with the measured table) and wait for "go" from the master (Ayush pastes it). After build and gates: the master issues a full QC, then freeze, then 1 paid run. If docs changed, say so in one line; no fresh blinds are required before QC on route 1.
