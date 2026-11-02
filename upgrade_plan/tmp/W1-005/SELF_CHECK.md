SELF CHECK, HELPER W1-005

Method: every quoted kit text in KIT_CHANGE.md was checked again by script against the rebuilt old files and the files read fresh from origin/main (git show origin/main:Input_Bundle_QC/<file>). OLD TEXT must be on that line of the old file and absent from that line of the new file. NEW TEXT and ADDED TEXT must be on that line of the new file. ADDED TEXT must be absent from that line of the old file.

QUOTE CHECKS

1. C1 05_Alignment_Integrity_QC.md:33 ADDED TEXT (450 characters, starts 'A set the delegation invokes uniformly is one prom'): CONFIRMED
2. C2 05_Alignment_Integrity_QC.md:96 OLD TEXT (159 characters, starts '- [ ] AL-2 every promise enumerated from `instruct'): CONFIRMED
3. C2 05_Alignment_Integrity_QC.md:96 NEW TEXT (206 characters, starts '- [ ] AL-2 every promise enumerated from `instruct'): CONFIRMED
4. C3 05_Alignment_Integrity_QC.md:38 ADDED TEXT (884 characters, starts 'Scope this to rules the bundle actually grades or '): CONFIRMED
5. C3 05_Alignment_Integrity_QC.md:38 OLD TEXT (44 characters, starts 'Fail; name the rule and the missing fixture.'): CONFIRMED
6. C3 05_Alignment_Integrity_QC.md:38 NEW TEXT (71 characters, starts 'Fail; name the rule, the check that claims it, and'): CONFIRMED
7. C4 05_Alignment_Integrity_QC.md:101 OLD TEXT (95 characters, starts '- [ ] AL-27 every stated rule has a fixture that a'): CONFIRMED
8. C4 05_Alignment_Integrity_QC.md:101 NEW TEXT (164 characters, starts '- [ ] AL-27 every graded rule has a fixture that a'): CONFIRMED
9. C5 Final_checklist.md:428 ADDED TEXT (445 characters, starts 'A set the delegation invokes uniformly is one prom'): CONFIRMED
10. C6 Final_checklist.md:459 ADDED TEXT (66 characters, starts 'the check id (one: the check that names the defect'): CONFIRMED
11. C6 Final_checklist.md:459 ADDED TEXT (187 characters, starts 'Several gates often describe the same condition fr'): CONFIRMED
12. C7 Final_checklist.md:490 ADDED TEXT (311 characters, starts 'Present means identifiable as the answer: a value '): CONFIRMED
13. C8 Final_checklist.md:491 OLD TEXT (31 characters, starts 'Two things are not this defect.'): CONFIRMED
14. C8 Final_checklist.md:491 NEW TEXT (33 characters, starts 'Three things are not this defect.'): CONFIRMED
15. C8 Final_checklist.md:491 ADDED TEXT (675 characters, starts 'A fact that genuinely feeds the rest of the work c'): CONFIRMED
16. C9 Final_checklist.md:492 OLD TEXT (180 characters, starts 'Each of those must either be stated in the instruc'): CONFIRMED
17. C9 Final_checklist.md:492 NEW TEXT (233 characters, starts 'Each of those must either be stated in the instruc'): CONFIRMED

OTHER CHECKS

1. rebuilt old 05 sha256 equals qc.json 5e81d67c...: CONFIRMED
2. rebuilt old Final_checklist sha256 equals qc.json aff7b002...: CONFIRMED
3. fresh origin/main files equal the copies used for the diff: CONFIRMED
4. lines differing old against new, 05: [33, 38, 96, 101] (expected [33, 38, 96, 101]): CONFIRMED
5. lines differing old against new, Final_checklist: [428, 459, 490, 491, 492] (expected [428, 459, 490, 491, 492]): CONFIRMED
6. line counts equal old against new for both files: CONFIRMED
7. 05:13 still says 'when one fires, report it under its CL id too': CONFIRMED
8. 05:89 CL-5 checklist line unchanged ('either stated in the contract or compared insensitively'): CONFIRMED
9. FC:491 still holds 'An instruction that states out loud that only an exact match counts has set that bar deliberately' (quoted by QC_FIX_PLAYBOOK_v3.md:55): CONFIRMED
10. FC:428 still holds 'name either the sentence it enforces or the shipped fact it reads' (quoted by LEVER_RULES_v3.md:36): CONFIRMED

RESULT

1. 27 of 27 checks confirmed.
2. The 10 unchanged kit files were not re-verified here; the caller's sha256 compare covers them.
3. Record line citations in STEP 3 (QC_FIX_PLAYBOOK_v3.md, QC_RULINGS.md, LEVER_RULES_v3.md, P2_build_v5.md, P12_recheck_fix_v5.md, P11_full_qc_v3.md) were read on branch claude/youthful-feynman-zug0uq at the time of writing.
