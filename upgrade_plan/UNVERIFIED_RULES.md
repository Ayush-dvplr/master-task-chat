UNVERIFIED RULES

Ayush, 3 Nov: do not assume any rule already in the records is correct. Each rule below touches one of the six problems. For each, Ayush says KEEP, CHANGE (with the new wording) or DROP. Until then it is UNVERIFIED and no plan step may rely on it.

This is the first batch. More batches follow (QC kit rules, template rules, lever rules) once these are done.

COMPACTION AND RECORDS (P1)
R1. The master chat only advises and writes prompts; all heavy work runs in other sessions. (GOALS Role)
R2. After any compaction, run the 7 step read order in master_chat_tasks/README.md before anything else.
R3. Only the master chat writes in master_chat_tasks, and only through the tools (issue.py, intake.py, status.py, pending.py, board.py). (README line 3)
R4. Every corrective remark from Ayush goes word for word into feedback.jsonl in the same turn; every master process failure goes to lessons.jsonl. (README lines 76 to 77)
R5. Store only rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries. (README "What gets stored")
R6. Handoff to Ayush is a table with board sha, step and a clickable file link; never "read and follow". (feedback 24 Oct 10:10, 31 Oct 11:00, 1 Nov)
R7. A session stays "issued" until Ayush says it is running. (feedback 2 Nov 00:24)

QC FIXES (P2)
R8. G1: never paste the QC "Fix:" text as the direction.
R9. G2: never move an assert into an existing check, never move weight onto a conduct or route criterion.
R10. G3: never delete a clause or grader without naming what grades the rest.
R11. G4: recheck every touched check against its rule list, one row each in RECHECK_FIX.md.
R12. G5: rerun the vacuity probe after fixes.
R13. G6: docs and TRUTH.md regenerated last, by script.
R14. G7: never regenerate tests without a byte diff of tests/ before and after.
R15. Caps: 2 fix rounds per QC, 2 QC rounds, drop rule at 3 edit rounds, 8 session time box. (README line 19)
R16. U12: stop at the first QC PASS; no hardening after a QC PASS.
R17. U13: a finding on lines unchanged since a passed round is reviewer noise; KEEP with diff evidence.
R18. Acceptance is zero QC findings including warns. (state.json targets.acceptance)

DOCKER (P3)
R19. Kill tests run in Docker only, with memory 4g and cpus 2, perl alarm. (README line 31)
R20. dockfree.py: 3 GiB headroom, unlimited container counts as 4 GiB, CPU cap 12.
R21. Max 5 busy workers (auto.py line 65), max 2 new builds per run, max 2 harness runs.
R22. A paid run starts only with 2 or fewer busy workers; at most 3 busy workers while it runs.
R23. Never harbor delete; images pruned only in idle cleanup. (state.json CLASH RULES)
R24. Paid runs at most 6 per day unless the plan says otherwise.

HARDENING (P4)
R25. Route 1 notes R0: primary lever kinds (a), (b), (c) only; at least 40% of positive test weight; misread rule levers are extras only.
R26. Gate: tests under 85, rubric under 85, final under 40, on 1 run of frozen QC passed bytes.
R27. Never rerun the same bytes after a missed gate.
R28. Difficulty comes from computation on hidden data, never from withheld rules. (GOALS G11)
R29. Honesty negative of minus 3 in every judge.
R30. Nothing in the docs announces a lever: no "note that", no trap list, no method word, no stated size bound. (route 1 R2)

TOKENS AND TOOLS (P5, P6)
R31. Workers run anthropic/claude-opus-5-5, variant high. (AUTO_POLICY Limits)
R32. GPT prompts in opencode must say "strictly do not run subagents". (feedback 31 Oct 16:12)
R33. Never hardcode generator or QC rules into prompts; prompts read the live files. (state.json rules)
R34. Allowed repos only Terminal_2.0_Harbor_Harness, Anubis_Tasks_Samples, beta-task-generator, Finalized_Tasks_RFP, read only. Ayush runs every pull, commit and push. (README Hard rules)
R35. Never edit the generator, the QC kit, "QC assigned/" or "my tasks/" without Ayush's explicit "proceed".
