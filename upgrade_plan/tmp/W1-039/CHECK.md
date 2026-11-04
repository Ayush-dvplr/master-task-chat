CHECK: EVERY DECISION ENTRY 40 TO 83 AGAINST PLAN_FINAL.md (W1-039, 4 Nov 2026)

Section letters are those of PLAN_FINAL.md (B items by number, F steps by number). COVERED = the plan carries it; PROCESS = a decision about this planning work that needs no change in the system; SUPERSEDED = replaced by a later entry that the plan carries.

1. ENTRY 40 (R1 brain, R2 smart loading, R3 to R10, R9 evidence): COVERED, B1 (RULES_IN_FORCE ROLE and AFTER COMPACTION, the card loads only live work), B2 (QC FIX STEPS R8 to R14), F1 and F2.
2. ENTRY 41 (Q112 accepted and checked, Q113 R9 keep, R11 to R20, R15, R18, R20 changed): COVERED, B1 (card points), B2, B12 (QC pass), B3 (dockfree only a fallback, R20), F7.
3. ENTRY 42 (Q114 no caps, Q115, R21 to R30, R28 open): COVERED, B4, B1 (caps are warnings), F1 (limits into settings); R28 closed by ENTRY 67.
4. ENTRY 43 (R31 to R35, R34 never commit or push, read only commands): COVERED, C3, D (upgrade.py never runs git), B6 (models per step), G5 (R32).
5. ENTRY 44 (card 6 KB, check over time): SUPERSEDED by ENTRY 45; the measurement is in B1 (CARD_TEST.md).
6. ENTRY 45 (Q118 option 3: 8 KB hard, 6 KB target, trims): COVERED, B1; upgrade.py checks the hard size (D).
7. ENTRY 46 (6.3 KB accepted, registry design field, targets 4 and 20, 3 hours): COVERED, B1, F6 (design field, a DATA migration with records restore as rollback).
8. ENTRY 47 (long running flag only reports, never stops): COVERED, B1; also E and SYSTEM_ID.md (no mc2 tool stops another process).
9. ENTRY 48 (Q8 history move, Q120 helper and caps as warnings, Q121 recovery accepted and verified): COVERED, B1, F1 (history move), F2 (recovery prompt, cold test), F6 (issue.py warnings).
10. ENTRY 49 (Q122 split, Q123 confirm four, Q124 triage then batches, Q125 fix map not bypass): COVERED, B1 (fold), B4, B2.
11. ENTRY 50 (Q126 decide it, rebuild hardness): COVERED, B2, I (goal check row P2).
12. ENTRY 51 (T1 to T10, T11 holes flagged): COVERED, B4 (BUILD_RULES from FOLD_DECISIONS.md).
13. ENTRY 52 (Q127 holes case by case): COVERED, B4.
14. ENTRY 53 (T12 to T21, design margin 5): COVERED, B4; settings design_margin checked by upgrade.py (D).
15. ENTRY 54 (T22, T23, T39, T40; anubis-stage-2 the only peer source): COVERED, B4, B8.
16. ENTRY 55 (T24 order, T26 to T34, T33 runs per task in settings, T25 recheck): COVERED, B4 (order in RULES_IN_FORCE), F1 (settings runs_per_task).
17. ENTRY 56 (Q128 T25 auto mode go, AUTO_POLICY batch): COVERED, F10.
18. ENTRY 57 (A1 to A13, one QC pass enough): COVERED, B12, F10.
19. ENTRY 58 (QC pass with false positive fails, minors, warnings; T35 to T46): COVERED, B12, B4.
20. ENTRY 59 (Q129 CL false positive passes; Q130 code quality criterion): COVERED, B12, B4 (BUILD_RULES RUBRIC).
21. ENTRY 60 (Q131 rules split): COVERED, B1.
22. ENTRY 61 (CR2 paid run program only; NO CORE 60 as a setting): COVERED, B4; settings no_core_keep_pct (F1).
23. ENTRY 62 (CR4, CR5 decided; CR3 asked again): COVERED, B4; CR3 by ENTRY 63.
24. ENTRY 63 (CR3 name the standard only): COVERED, B4.
25. ENTRY 64 (P13 intake request; flag on author change): COVERED, B13, H.
26. ENTRY 65 (Q132 three kinds, provenance, counts, never edit authors): COVERED, H1 to H3.
27. ENTRY 66 (Q133 Ayush judges false positives from the QL triage table; QL step before the paid run): COVERED, B2, B12, H5, F4 (QL triage template).
28. ENTRY 67 (R28 keep, worded to match T7; Q37 closed): COVERED, B4; Q37 PROCESS.
29. ENTRY 68 (Q134 a to f; QC fast lane): COVERED, B3, F7 (dockfree first, then measure), F8 (switch, fast lane check), F10 (paid runs wrapped, daemon started by auto.py). Q134 (d) "stop --now leaves the daemon running" and (e) "session limits stay separate from Docker room" are carried by the drafts (T/W1-031/DESIGN.md), not restated in the plan: COVERED by link.
30. ENTRY 69 (Q135 1 to 10: settings keys, retired template refused, honesty negatives, probe band, lever_keep_pct 90, retire P3, P5, P6, update P4, snapshot with text, fingerprints folder, LENIENT acts freely, new check id MAJOR by default): COVERED, B2, B10, F1, F3, F5, B19 (S3, S7).
31. ENTRY 70 (S9 runner record, four options, default Opus 5.5): COVERED, B19 (S9), G4, F6.
32. ENTRY 71 (Q136: limits are the pain; blinds Opus 5; no cheaper models; Codex read only plus steps named in PLAN.md; Codex subagents yes, GPT no; DONE any case; DCP off measured 1 week): COVERED, B5, B6, B19 (S5), G4, G5, J7 (e).
33. ENTRY 72 (Q137: family order, prototype signal only, failed card switches, idea queue, design_cards.jsonl, research INTAKE, teammate study in its own session; Q138 later): COVERED, B9, B11, F6, J2.
34. ENTRY 73 (Q139: outside run counts only if exact; assigned not counted unless said; blinds Opus 5 and rest 5.5 when unnamed; keep the author name; Q140 later): COVERED, H3, H4, B19 (S9), J2.
35. ENTRY 74 (P14 to P17 recorded): COVERED, B14 to B17, C, D, E.
36. ENTRY 75 (Q141 git for system only; Q142 built in upgrade with checks and rechecks; Q143 checklist; Q144 unique prefix and hash): COVERED, C, D, E; Q143 PROCESS (done by ENTRY 77).
37. ENTRY 76 (Q145 print commands only): COVERED, D, UPGRADE.md.
38. ENTRY 77 (Q146 all questions to PL and QL, plain words with scenarios): COVERED, B15 (PROCESS, file sent).
39. ENTRY 78 (P18 drop the generator, two stages, bundle structure): COVERED, B18, F9.
40. ENTRY 79 (Q148 own skeleton, Q149 design pack outside the bundle, Q150 BR-SL in stage 1, Q151 no PL generator question): COVERED, B16, B18, F9; Q151 PROCESS.
41. ENTRY 80 (remove "What Ayush does today" from PL_QUESTIONS.md): PROCESS, done in PL_QUESTIONS.md.
42. ENTRY 81 (remove PL31): PROCESS, done.
43. ENTRY 82 (kit more lenient; RQ10; PL questions sent; DR3 and the line still apply): COVERED, B19 (S7), J3, J7 (d).
44. ENTRY 83 (kit 487b4697 classified, BUILD_RULES and fix map updated): COVERED, B2, B19 (S7), F5 (new snapshot on Ayush's word).

DECISIONS THE PLAN MISSES
None missed outright. Two are carried only by a link to a draft rather than stated in the plan (ENTRY 68 Q134 (d) and (e)), and one needs work that is not drafted yet: the P18 skeleton folder and the stage 1 and stage 2 templates (ENTRY 78, 79) are decided but written only at F9, after PROCEED.

POINTS RAISED WHILE CHECKING (not decisions, for Ayush)
1. ROOT name, the backup folder outside ROOT, and where branch v2 and the tags live (local only or GitHub) are not yet decided (UPGRADE.md OPEN POINTS).
2. The system id mc2 is a proposal; Q144 chose "unique prefix and hash" but not the word.
3. The harness queue removes containers by task name (SYSTEM_ID.md E3): the standing rule "the same task never runs in both systems at once" is new and needs Ayush's yes.
4. The new root opencode.jsonc switching opencode-kiro off is the coordinator's wording for this plan; whether a project config can switch off a global plugin is UNVERIFIED (Q78).
