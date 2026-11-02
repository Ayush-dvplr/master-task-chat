SELF CHECK (helper W1-003)

Method: after writing ANSWERS_FROM_RECORDS.md and MISSING.md, every citation below was reopened with sed -n '<line>p' on the cited file and the text compared with what the answer claims. MCT = master_chat_tasks/, MCW = master_chat_work/.

CONFIRMED (reopened, text matches the claim)
1. MCT/feedback.jsonl:1 (23 Oct 01:01): "second oen also got 100, 100, 100 so I am stopping". Used in Q35.
2. MCT/feedback.jsonl:10 (24 Oct 12:52): master kept re-introducing a 35 cap; "There is NO cap". Q7, Q30.
3. MCT/feedback.jsonl:20 (27 Oct 13:28): "My fix v6 prompt caused 2 of QC v7 findings". Q12.
4. MCT/feedback.jsonl:21 (27 Oct 14:40): Mac froze, 3 orphan python processes about 185 GB, swap 76.8/77.8 GB. Q18.
5. MCT/feedback.jsonl:33 and :35 and :36 (1 Nov 11:2x, 2 Nov 00:24, 2 Nov 20:01). Q7.
6. MCT/lessons.jsonl:56, :57 (23 Oct 08:48), :72 (24 Oct 00:40), :82 (24 Oct 11:15), :87 (24 Oct 21:36), :89 (1 Nov 11:27), :95 (2 Nov 13:15), :100 (2 Nov 16:31), :107, :108, :109 (2 Nov 22:38), :110 (2 Nov 23:25). Q7, Q11, Q12, Q17, Q22, Q35.
7. MCT/log.jsonl:162 (23 Oct 14:58, /tmp/blind), :164 (24 Oct 01:05, 9fe2a50 and f99c855 issued), :166 (24 Oct 01:20, S25 on P9 v1). Q10, Q39.
8. MCT/decisions.jsonl:30, :53, :57, :59, :86, :88, :90, :103, :112, :115, :123, :146, :156, :159, :201, :202, :203, :206, :211, :228, :259, :265, :319, :336, :363, :364, :409, :413, :415, :416, :418, :455, :503, :504, :514, :589, :603, :609, :627, :650, :661, :704, :706, :716, :717, :735, :737, :738, :739, :751, :753, :762. Each line reopened; time and content match the answers.
9. MCT/registry/scores.jsonl:40, :43 (100/100/100), :49, :50 (valid false, permission bug), :78 to :93 (tests 100 except :79 and :91), :113 (flood a1 100/13.33), :116 (last line, 2 Nov 17:51). Q1, Q35.
10. MCT/state.json:2 (updated_ist 24 Oct 11:28), :29 (caps 35), :31 (old gate 100/100/70), :34 (1 run push), :38 (P1 v1), :49 (P12 v4), :60 (8 runs on final approval), :79 (Docker-heavy max 2), :125 (_scope), :126 (gate v3.7). Q1, Q17, Q30 to Q33, Q39.
11. MCT/README.md:5 (read order after compaction), :31 (old gate, P12 v4, one Docker task at a time), :71 (never edit QC assigned or my tasks). Q7, Q17, Q31, Q39, MISSING.
12. MCT/GOALS.md:9 (G1 compaction) and :34 (1 run, Ayush 27 Oct 17:17). Q7, Q33.
13. MCT/auto/AUTO_POLICY.md:47 (dockfree replaces the 27 Oct max 2) and :57 (16 GiB). Q17.
14. MCT/knowledge/INDEX.md:15 (dockfree ACTIVE 31 Oct) and :16 (P12 v5 ACTIVE 31 Oct, v4 SUPERSEDED). Q17, Q31.
15. MCT/prompts/templates/CHANGELOG.md:7, :11, :23, :41, :43, :49, :55, :56. Q31, Q32, Q35, Q39.
16. MCT/auto/auto.py:67 MAX_HARNESS = 2. Q17.
17. MCT/prompts/templates/P13_blind_solve_v2.md:7 (_runs blind copy), P9_harden_from_results_v4.md:52 (OUT/agent_program), _COMMON_RULES_v5.md:17 (30 Oct reboot wiped /tmp), P12_recheck_fix_v5.md:3 (fix receipt, "fixes often break something new"). Q10, Q12, Q31.
18. MCT/prompts/issued/_adhoc/20261101_route1_notes.md:11 (saved input under WORK/). Q10.
19. MCT/knowledge/QC_FIX_PLAYBOOK_v3.md:3 (TS-23 option A, 67 of 255). Q30.
20. MCT/knowledge/KNOWLEDGE.md:5 (team flow, 8 runs at final approval). Q33, MISSING.
21. MCT/board.json:5555 (updated 3 Nov 00:10) and pending.db history max 3 Nov 00:10 for S440. Q1.
22. MCW/20261025_process/leak_audit_ed0bc62/LEAK_AUDIT.md:22 (contract sentence states the whole graded procedure, 7 of 8 bundles). Q22, Q35.
23. MCW/_dev_research/qc_loop_analysis/3b00450/ANALYSIS.md:14, :17, :22, :180 (67 FIX_CAUSED, 37 HARDEN_CAUSED, 42.0% own edits, at least 22 directed by the prompt). Q12, Q22.
24. MCW/20261023_sentinel-policy-recompute/harden_r1/DIAGNOSIS.md:21 and harden_r2/DIAGNOSIS.md:21; MCW/20261023_cohort-retention-reconciliation/harden_r2/DIAGNOSIS.md:22 and :28. Q11.
25. MCW/bundles/_work/hangar-check-replan/LOG.md:6, :20, :68, :100, :106, :129. Q10, Q16.
26. MCW/bundles/_work/flood-repair-portfolio/LOG_harden_c3aca8d.md:5 and :13; MCW/bundles/_work/metered-usage-rating-pipeline/LOG.md:168; MCW/bundles/_work/sensor-network-lsq-correlated-adjustment/LOG.md:7; MCW/bundles/_work/flood-repair-portfolio/LOG.md:2 (3 Nov 00:36) and :4 (3 Nov 00:08). Q1, Q16.
27. MCT/auto/runs/20261027T2239_overnight/REPORT.md:20 and :30; 20261027T0200_night/REPORT.md:38 and :47; 20261027T2031_evening/REPORT.md:8. Q10, Q16.
28. MCW/20261029_schema-migration-plan-repair/p12_fix_v12_08741c4/RECHECK_FIX.md:95 and p12_fix_v13_6ebf33a/RECHECK_FIX.md:83 (lever before/after table). Q11.
29. MCW/20261030_upgrade2/S2_folders/PATH_REFS.csv:1013 (codex_oauth/credentials.py reads ~/.codex/auth.json). MISSING secrets.
30. MCW/20261024_process/MASTER_UPGRADE_PLAN_v1.md: header dated 24 Oct 11:15, "APPROVED 24 Oct 11:26" (line 5), "60% of new QC findings came from our own edits" (line 10). Q12, Q35.
31. git log: commit 10d3e3ff dated Tue Nov 3 00:45:28 2026 +0530 is the only commit that touches master_chat_tasks/. Q1.
32. MCW/20261102_hangar-check-replan/harden_r1/gate_run_a1/result.json: verifier_result.rewards.reward 0.75, trial under Terminal_2.0_Harbor_Harness/.kiro-run-hangar-check-replan-20261102T002009. Q10, Q35.

CORRECTED DURING THE CHECK
1. Q22 first said decisions.jsonl:200-201 for the metered and config ROUND LIMIT lines; reopened, they are :201 and :202. Fixed.
2. Q35 first said decisions.jsonl:204 for "every shape leaked tonight"; reopened, it is :203 (25 Oct 08:13). Fixed.
3. Q35 first also cited decisions.jsonl:108 for the plan approval; :108 is the Q55 schema answer, not the approval. Removed.
4. Q16 first said "15 work files" with START=no; recount gives 13 files in master_chat_work. Fixed.
5. Q10 first said "about 30" agent_program folders; recount gives 28. Fixed.

COULD NOT CONFIRM (left marked UNVERIFIED in the answers)
1. Q35: which of the two episodes (24-25 Oct habit levers, or 31 Oct-2 Nov misread-rule levers) Ayush means by "2 whole days". The records support both; only Ayush can say.
2. Q31 and Q39: whether the short fix prompts issued from 1 Nov 11:27 on left out the P12 v5 fix receipt on purpose (route 1) or by template drift. The prompts do not say which template they were filled from.
3. Q12: that no fix ever broke oracle or nop. I found no record of it, but a session may have repaired it internally without writing it down.
4. Q11: that reading the diff was never the way a lost lever was found. Not seen, not proven absent.
5. Q7 point 5: whether the older repeats (35 cap, "Read and follow") came right after a compaction. The records do not say.
6. Q33: who starts the 8 runs at final approval (team or Ayush).
7. MISSING: whether the two bridge keys in the gate_run_a5 wrapper.log files are still valid, and whether AGENTS.md at the Terminal Bench root is loaded into sessions.
8. Q1: whether the Mac copy of registry/scores.jsonl is newer than the repo copy (the depot a1 and hangar a1 lines are missing here).
