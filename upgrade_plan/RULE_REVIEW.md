RULE REVIEW (builds RULES_IN_FORCE.md for the master's state card; Q4 and Q110)

Each rule from UNVERIFIED_RULES.md gets Ayush's word: KEEP, CHANGE (new wording), or DROP. Claude adds a note and a suggestion; Ayush decides. Batches of about 10.

BATCH 1 (R1 to R10), asked 3 Nov
R1. The master chat only advises and writes prompts; all heavy work runs in other sessions.
  Note: matches DR1 (token light) and how this upgrade session works. Suggest KEEP.
R2. After any compaction, run the 7 step read order in master_chat_tasks/README.md before anything else.
  Note: the 7 step order loads about 100 KB and still lost rules (F1.1, F1.3). P1 replaces it with STATE_CARD.md plus on demand reading. Suggest CHANGE to: "After any compaction, read STATE_CARD.md first, then only what the next step needs."
R3. Only the master chat writes in master_chat_tasks, and only through the tools.
  Note: keeps records clean; the state card generator becomes one more tool. Suggest KEEP.
R4. Every corrective remark from Ayush goes word for word into feedback.jsonl in the same turn; every master process failure goes to lessons.jsonl.
  Note: the same lesson was logged twice and not followed (F1.3). Suggest CHANGE: add "a lesson that repeats becomes a tool check, not another note".
R5. Store only rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries.
  Suggest KEEP.
R6. Handoff to Ayush is a table with board sha, step, status and a clickable file link; never "read and follow".
  Note: already printed in the state card. Suggest KEEP.
R7. A session stays "issued" until Ayush says it is running.
  Suggest KEEP.
R8. G1: never paste the QC "Fix:" text as the fix direction.
  Note: the study 3b00450 found many later findings caused by fixes, mostly from pasted Fix text (F2.1). Suggest KEEP.
R9. G2: never move an assert into an existing check; never move weight onto a conduct or route criterion.
  Note: Claude has no evidence for or against from the cards. Ayush's call.
R10. G3: never delete a clause or grader without naming what grades the rest.
  Note: protects against silent loss of a lever in a fix (P2). Suggest KEEP.
Decisions (Ayush, ENTRY 40, 3 Nov):
R1 CHANGED to: "The master is the brain of the system, not just a prompt generator and record keeper. It plans the next step; writes and tunes prompts; sends all heavy work to other sessions; verifies every session result on disk before recording it; flags to Ayush anything wrong, missing or contradictory; and tells Ayush about updates (finished sessions, QC kit changes, new findings)."
R2 CHANGED to: "After any compaction, read STATE_CARD.md first. Load only what is live: open items, open issues, running and issued sessions, and items changed recently; never the full history of long completed work. Read more only when the next step needs it." Improvements: see R2 IMPROVEMENTS below (Q112).
R3 KEEP. R4 CHANGED as suggested ("a lesson that repeats becomes a tool check, not another note"). R5 KEEP. R6 KEEP. R7 KEEP. R8 KEEP. R10 KEEP.
R9 EVIDENCE (Claude, 3 Nov): study master_chat_work/_dev_research/qc_loop_analysis/3b00450/ANALYSIS.md lines 59 to 60: a fix prompt that moved an assert into the config criterion caused a TS-13 finding, and one that moved rubric points from R6 to R7 to R9 caused a JD-15 finding; in the same study TS-13 appears 17 times and JD-15 10 times among later findings. The kit rules: TS-13 "One property per test" (03_Tests_QC.md line 44); JD-15 limits what a criterion may require (04_Judge_QC.md line 92). Suggest KEEP (Q113). DECIDED: KEEP (ENTRY 41).

R2 IMPROVEMENTS (Claude suggestions, Q112)
1. The state card lists only live things: running and issued sessions, open items, active tasks, and anything that changed in the last 48 hours. Closed work is never loaded.
2. "Since last card" block: what changed since the previous card (finished sessions, new scores, new QC results), so the master sees news first.
3. One task on demand: tools/status.py <slug> prints a single task card; the master reads it only when working on that task.
4. Decisions in force: a generated DECISIONS_ACTIVE.md with only the decisions still in force (superseded ones marked and left out); decisions.jsonl (278 KB) is never read whole.
5. Feedback and lessons distilled: their rules go into RULES_IN_FORCE.md; the raw feedback.jsonl and lessons.jsonl are not read after compaction.
6. A size budget enforced by the script (the card warns above 4 KB).
7. Each line of the card carries its source file, so the master can open exactly one file when it needs detail.
ACCEPTED by Ayush (Q112, ENTRY 41).

R2 CHECK AGAINST THE GOAL (Claude, 3 Nov)
The goal is many accepted tasks, fast, with a master that is a brain (R1) and light on tokens (DR1). Points 1 to 7 serve that: they cut what the master reads after compaction and put news and live work first. Two risks found and fixed:
  a. "Changed in the last 48 hours" could hide an old item that is blocked and waiting for Ayush. Fix: blocked items and questions waiting for Ayush are always shown, whatever their age.
  b. The 4 KB limit can push useful lines out. Fix: the card fills in a fixed priority order (rules, news, waiting for Ayush, running, active tasks, the rest) and says what it left out.
MISSING, added (Q115):
8. Sessions running longer than expected are flagged (so the master can chase them, per R1).
9. QC kit status line: the kit fingerprint compared with the stored snapshot, and LENIENT, MINOR or MAJOR if it changed (S7, R_QC_UPSTREAM).
10. Settings line: the current gate and caps, read from the one settings file (DR2), so every session uses the same values.
11. Progress line: tasks pushed today and this week against the target, since the goal is volume.
12. Questions to Ayush older than 12 hours are listed first (the existing U7 rule).
13. Uniqueness reminder: the lever kinds and design shapes used in the last few tasks, so a new build does not repeat them (G9, goal item 6).


BATCH 2 (R11 to R20), asked 3 Nov
R11. G4: recheck every touched check against its rule list, one row each in RECHECK_FIX.md.
  Note: the 3b00450 study says 45 of 67 fix caused findings carried a rule id a recheck pass would test. Suggest KEEP, done by script where possible.
R12. G5: rerun the vacuity probe after fixes (the unchanged shipped tool and data must not pass any positive check).
  Suggest KEEP.
R13. G6: docs and TRUTH.md regenerated last, by script.
  Suggest KEEP.
R14. G7: never regenerate tests without a byte diff of tests/ before and after.
  Note: this is the base of the P2 lever regression gate. Suggest KEEP.
R15. Caps: 2 fix rounds per QC, 2 QC rounds, drop at 3 edit rounds, 8 session time box.
  Note: with an AI QC that finds something every run (P12), a hard cap of 2 QC rounds may stop good tasks. Suggest CHANGE to settings (like the gate), with the values Ayush wants.
R16. U12: stop at the first QC PASS; no hardening after a QC PASS.
  Note: QC PASS now means the working definition of Q95. Suggest KEEP.
R17. U13: a finding on lines unchanged since a passed round is reviewer noise; keep the code, with the diff as evidence.
  Note: fits Q95 (false positive review). Suggest KEEP.
R18. Acceptance is zero QC findings including warns.
  Note: contradicts Q95 (minors accepted if they do not repeat) and the count cap warn above 35. Suggest CHANGE to the Q95 definition.
R19. Kill tests run in Docker only, memory 4g, cpus 2, perl alarm.
  Note: the 27 Oct hang came from solvers run on the host, outside Docker (Q65b). Suggest KEEP.
R20. dockfree.py: 3 GiB headroom, a container without a limit counts as 4 GiB, CPU cap 12.
  Note: to be replaced by the background Docker slot script (S1, P3), which measures real use. Suggest CHANGE: keep as a fallback until S1 exists.
Decisions (Ayush, ENTRY 41, 3 Nov): R11 KEEP, R12 KEEP, R13 KEEP, R14 KEEP, R16 KEEP, R17 KEEP, R19 KEEP.
R15 CHANGE: the caps become settings (values asked in Q114).
R18 CHANGE to: "A task is QC passed by the working definition (Q95): no fail finding in 2 QC runs in a row, any CL fail blocks, a minor is accepted if it does not come back with the same evidence, and a false positive review follows every QC result."
R20 CHANGE to: "dockfree.py stays only as a fallback until the background Docker slot script (S1) exists; then S1 decides, from real use."

BATCH 3 (R21 to R30), asked 3 Nov
R21. Max 5 busy workers, max 2 new builds per auto run, max 2 harness runs.
  Note: fixed numbers in auto.py; the waiting problem (P3). Suggest CHANGE to settings, decided by the S1 script and Ayush.
R22. A paid run starts only with 2 or fewer busy workers; at most 3 busy workers while it runs.
  Suggest CHANGE to settings, same as R21.
R23. Never harbor delete; Docker images pruned only during idle cleanup.
  Suggest KEEP (protects running jobs and results).
R24. Paid runs at most 6 per day unless the plan says otherwise.
  Note: a cost setting. Suggest CHANGE to a setting with Ayush's value.
R25. Route 1 R0: primary lever kinds (a), (b), (c) only; at least 40 percent of positive test weight; misread rule levers are extras only.
  Note: CR7 already changed the last part (misread rule allowed as primary with one deciding sentence). Layer F adds D5, D6, D8, D9 families. Suggest CHANGE to: "primary lever from the PATTERNS.md DESIGN families, at least 40 percent of positive test weight, firing in most hidden inputs."
R26. Gate: tests under 85, rubric under 85, final under 40, on 1 run of frozen QC passed bytes.
  Note: already a setting (DR2). Suggest KEEP as the current setting value.
R27. Never rerun the same bytes after a missed gate.
  Suggest KEEP (a rerun of the same bytes only buys a lucky score).
R28. Difficulty comes from computation on hidden data, never from withheld rules.
  Note: matches DR3 and the agreed line (GOAL item 7). Suggest KEEP.
R29. An honesty negative of minus 3 in every judge.
  Note: the cards show it fires (for example 7e0d8feb R31 minus 3, 9f5486ac R9 minus 3). Suggest KEEP.
R30. Nothing in the docs announces a lever: no "note that", no trap list, no method word, no stated size bound.
  Note: Layer F found that fd7a2544 states the hidden size and still lost 64 of 86 points (CONFIRM.md). Suggest CHANGE: drop "no stated size bound" when a runtime lever needs it; keep the rest.
Decisions: (open)
