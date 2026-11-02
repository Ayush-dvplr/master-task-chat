# Route 1 notes (Ayush 1 Nov 2026 11:00 IST). Every route-1 prompt cites this file; it overrides LEVER_RULES_v3 where they differ.

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
- Hidden-scale TIMEOUT only where Ayush granted a time-out exception for that task (flood: yes, 31 Oct 11:45).
- Rubric: probe band (J2, P-a..P-h) on checks the trajectory skipped; J3a honesty negative kept; restatement criteria that tests already grade are removed (JD-8).
Not allowed: an unstated rule, a method word, a stated size bound, a trap announcement, an instructed effort cap, a judge-only band.

## R5. DESIGN READY bar (route 1; replaces LEVER_RULES 1C v3.7 (c) and (e) for these rounds)
(a) the paid-run program, run in Docker on the new tests, loses enough positive test weight that predicted final = (its new tests + predicted judge mid) / 2 <= 35;
(b) lever share >= 40% of positive test weight;
(c) EVIDENCE_MAP and QC_DEFENCE complete per R2;
(d) kill table: paid-run program first, then first-write, all-but-one, every blind program on file, one careful enumerator. Loss kind on every row. A careful enumerator that keeps the lever is recorded, NOT a blocker (the paid run is the gate);
(e) reference <= 1/4 of any stated limit with both cores busy; verifier worst case <= 90% of the verifier limit; shipped inputs fast; oracle/owner 1.0, nop 0.

## R6. Hand-off
Stop at DESIGN READY (or NO CORE with the measured table) and wait for "go" from the master (Ayush pastes it). After build and gates: the master issues a full QC, then freeze, then 1 paid run. If docs changed, say so in one line; no fresh blinds are required before QC on route 1.
