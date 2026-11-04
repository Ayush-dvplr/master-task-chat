CHANGES IN PLAN_FINAL.md (W1-042, 4 Nov 2026). Source: upgrade_plan/PLAN_FINAL.md (W1-039). Cold test: upgrade_plan/tmp/W1-040/COLD_TEST.md sections 5 and 6. Decisions added: ENTRY 84 and 85 in upgrade_plan/ANSWERS.md. Section letters below are those of the new plan, upgrade_plan/tmp/W1-042/PLAN_FINAL.md.

COLD TEST SECTION 5 (unclear, vague, contradictory, broken links)

1. 5a CHECK.md path: now upgrade_plan/tmp/W1-039/CHECK.md for ENTRY 40 to 83; ENTRY 84 and 85 placed by section in the coverage line. FIXED.
2. 5b fingerprints: ROOT/master_chat_tasks/knowledge/fingerprints/, with today's place master_chat_tasks/knowledge/fingerprints/ (B19, F5). FIXED.
3. 5c CARD_TEST.md and TEST.md: full paths upgrade_plan/drafts/P1/CARD_TEST.md and upgrade_plan/tmp/W1-031/TEST.md; every other linked file also given from the repo root (PATHS line). All existing paths checked with ls; the four not yet existing are ROOT paths, carry_over.py (TO BE DRAFTED), upgrade_plan/tmp/W1-041/MAP.md (in progress) and this file. FIXED.
4. 5d which knowledge folder: FIX_MAP.md goes into ROOT/master_chat_tasks/knowledge/ (F1); upgrade_plan/knowledge/ is named in full where meant. FIXED.
5. 5e statuses: one list of seven defined at the top (DRAFTED, TESTED, DECIDED, TO BE DRAFTED, IN USE, WAITS AYUSH, WAITS MAC) and only those used; "TESTED dry", "in use", "Q140 later" replaced. FIXED.
6. 5f git creation and first tag: C2 says ROOT is a clone of the new GitHub branch stable; first tag mc2-v2.0 at step 0; step N is tag mc2-v2.N, so step 0 now has a tag. FIXED.
7. 5g archive: F5 names ROOT/master_chat_tasks/knowledge/fingerprints/archive_<old head8>/qc.json and the rollback copies it back. FIXED.
8. 5h backup and command: F6 rollback is the previous tag, then the rsync printed by upgrade.py from BACKUP/<day of step 6>/records/, dry run first; BACKUP is outside ROOT (C4). FIXED.
9. 5i DCP files by git or by hand: by the git checkout (C3, F2); by hand only the master start and the checks (G5); step 2 rollback removes them through the checkout. FIXED.
10. 5j master_queue.py wrap undesigned: moved into STAGE B BLOCKERS 1, blocking steps 8 and 10, with R35. FIXED.
11. 5k DCP layering stated as fact: G1 marked UNVERIFIED until the step 2 Mac check, with a rollback if the nearest file does not win. FIXED.
12. 5l which GPT prompts: S5 now says Codex research may use subagents and the GPT runner oc-gpt-sol-6.1 never does, so its prompts carry the R32 line (B19). FIXED.
13. 5m 90 percent: of the positive test points each lever's wrong reading lost before the fix (B2). FIXED.
14. 5n 40 percent: of the task's positive test weight carried by the primary lever (B4). FIXED.
15. 5o 406k to 184k: written as "fall from about 406k to about 184k tokens" (B5). FIXED.
16. 5p "long sessions only reported": a long running session shows as LONG and is only reported, never stopped (B1). FIXED.
17. 5q "DONE in any case": intake reads a result status in any letter case (B6). FIXED.
18. 5r SYSID and "P2 v5 route": SYSID defined in E3; step 9 rollback now says the one session build template P2_build_v5. FIXED.
19. 5s "compression count only Ayush's": G1 says every compression in a day was started by Ayush. FIXED.
20. 5t four runners: named in B19 (oc-opus-5.5, oc-opus-5, codex-sol-6.1, oc-gpt-sol-6.1). FIXED.
21. 5u rule ids: RULE IDS list, one line per family (P, S, Q and RQ, DR, R, T, CR and C, A, BR-SL, CL, IN, DS, D, PL and QL). FIXED.
22. 5v goal check rows: P8, P12, P14, P15 added; the table became a numbered list (no dash table rows). FIXED.
23. 5w mc2 and ROOT name: mc2 DECIDED (Q153, E1). ROOT name is picked by Ayush at step 0; the plan says nothing depends on it because everything reads it from settings (C1). FIXED for mc2; ROOT name stays Ayush's choice at step 0 by design.

COLD TEST SECTION 6 (risky decisions)

24. 6a QC pass on Ayush's own judgment: B12 restates the exact rule (one complete pass; a fail is not blocking only as a false positive Ayush marks from the triage table with diff and kit line, or an IN-17 fail he waives under kit 487b4697; real fails fixed; minors and warns as PL notes; QL review follows; RQ11 may adjust). FIXED.
25. 6b CR7 close to the line: B8 states the test (one clear deciding sentence in the shipped docs, checked by the stage 1 leak check and DESIGN READY; DR3 absolute). FIXED.
26. 6c two sets of records: C5, ENTRY 85: new records are the truth from day 1; old running tasks finish there and carry_over.py (TO BE DRAFTED) copies their results once. FIXED.
27. 6d guard is memory only: E2 standing rule Q154 with warnings from upgrade.py preflight and the state card; the harness guard is STAGE B BLOCKER 1. FIXED.
28. 6e teammate counts need the PL: Ayush chose "Your word only" (ENTRY 85); H3 keeps it. NOT CHANGED, by Ayush's decision.
29. 6f C3 to C44 undecided: F says a helper maps them now (upgrade_plan/tmp/W1-041/MAP.md) and the leftovers come to Ayush in one batch before STAGE A starts and before BUILD_RULES.md goes in at step 1. FIXED.
30. 6g approving undesigned steps: two stage approval; STAGE A steps 0 to 5 with PROCEED, STAGE B steps 6 to 10 after four explicit blockers and a second approval (F). FIXED.
31. 6h DCP off cost with no revert threshold: J1 says the week's numbers go to Ayush, who decides; no number is set. PARTLY: no threshold was decided by Ayush, so none is invented.
32. 6i PL answers change BUILD_RULES after approval: A and J1 say a PL answer that would loosen CL-1 to CL-10, DR3 or the agreed line comes to Ayush as a decision first. FIXED.

DECISIONS ADDED (ENTRY 84, 85)

33. Q152: C2 (branches stable and v2 and tags on GitHub, clone into ROOT, first tag mc2-v2.0), C3 (data out of git), C4 (daily backup outside ROOT, proposed mc2_backup next to ROOT).
34. Q153 and Q154: E1, E2, D (preflight warning).
35. Q155: G6 compact prompt (MASTER_RECOVERY part E) then restore prompt (part B), works because the master's DCP is manual; protect tag marked extra only.
36. Q156: B10, E3 ([[ROOT]] fill token, part of P17).
37. ENTRY 85: C5 records truth and carry_over.py, H3 counts unchanged, F two stages with STAGE B BLOCKERS, F note on C3 to C44.

LENGTH: PLAN_FINAL.md is 3035 words by wc.
