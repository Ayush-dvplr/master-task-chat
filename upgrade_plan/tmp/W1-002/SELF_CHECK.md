SELF CHECK OF CITATIONS (helper W1-002, 2 Nov 2026)

Method: for each constraint below, every cited line was reopened with sed -n "<line>p" on the file named in CONSTRAINTS.md (source keys as there) and compared with the claim. Line numbers for jsonl files are JSON line numbers. Three citation slips were found while checking and fixed before this file was written (see FIXED DURING CHECK).

CHECKED, CONFIRMED (36 constraints across all 10 themes)

Lever design
1. H1: RN:5 says "Primary lever, at least one per task, carrying >= 40% of positive test weight, that the CAREFUL EXACT PROGRAM loses". Confirmed.
2. H6: RN:8 says "(c) measured scale: hidden inputs inside the documented schema, one stated runtime sentence (no method word), reference <= 1/4 of the limit with both cores busy, the careful program >= 4x the limit". Confirmed.
3. H9: RN:9 says misread-rule held-out branches "are EXTRAS ... never count them toward the 40%". Confirmed.
4. H10: RN:11 says every lever names oracle branch, program branch and a saved input; "No named difference = no lever". Confirmed.
5. H11 and H12: RN:12 says "Careful program keeps >= 60% of primary lever points = NO CORE" and the 2,000 variant park test. Confirmed.
6. H24: RN:17 says "A blind or paid program that wins is the guide for the harden, never a reason to park" and "Nothing is parked except on Ayush's word" (line continues). Confirmed.
7. H28: RN:13 lists the four never-copy items. Confirmed.
8. H29: LR:86 says stated-rule levers "(L1-L11, S1, S3, S5, S6, H1-H9, T1-T4) are PAUSED". Confirmed.
9. H32: LR:93 includes "odd carriers and format rules" among rejected sources. Confirmed.
10. H33: LR:133 says "Plain decoys, look-alike files, encodings, DST, duplicate ids and superseded notes are noise only". Confirmed.
11. H34: KN:66 lists "resource pressure" under "Does not work". Confirmed.

Hiding and leaks
12. H38: RN:20 says "Every hidden check, held-out instance and lever stays in tests only ... no stated size bound". Confirmed.
13. H39: CR:27 (Never 8) bans "not only X", "note that", "be careful", trap lists, rule counts. Confirmed.
14. H40: CR:28 (Never 9) bans author notes incl. TRAP, lever, inverse, decoy, grader, hidden test, answer key. Confirmed.
15. H44: LR:150 (W5) says separating cases are in hidden reseeded inputs only except L5, with BRANCH_FIRE. Confirmed.
16. H48: P13:8 says the prompt "must contain no lever names, rule hints, trap words or scores"; P13:7 copies only instruction.md and environment. Confirmed.

Instruction wording
17. H56: RN:10 quotes "Each output document is graded whole, and only an exact match counts" and Final_checklist.md:491. Confirmed.
18. H58: RN:14 keeps "Leave enough of that time to finish and write your final reply." and "No effort cap". Confirmed.
19. H59 and H60: P2:121 (N seconds sentence, online-lookup sentence) and P2:122 (never mention tests, grader ..., under 6000 characters). Confirmed.
20. H61: LR:170 (G8a) states the exact command rule. Confirmed.
21. H67: CR:58 says "at least 3x the oracle's measured time". Confirmed.

Tests and weights
22. H86: LR:173 (G11) RULE_COVERAGE one row per AL-2 unit and ordering. Confirmed.
23. H88: KN:9 weights in {+-1, +-3, +-5}; LJ:94 "Kit W2 allows test weights 1,3,5 only"; LJ:108 never lower a core check while adding lever checks. Confirmed.
24. H89: KN:39 (no upper cap, floors 10 and 8) and PB:41 (TS-23 keep as warn). Confirmed.

Judge rubric
25. H99: LR:180 (J1) "No figure criterion, what-if or not". Confirmed.
26. H100: LR:181 (J2) 8 to 16 probes, w3, 55 to 70%. Confirmed; DJ:762 "no judge probes" exception confirmed.
27. H103: LR:200 J3 heading with "judge_qc J10 rejects 'not'". Confirmed.
28. H105: LR:204 (J4 behavioural wording) and PB:50 (different "Python reviewer" wording). Confirmed, and the conflict C9 stands.

QC rules and fix process
29. H114: CR:64 "pass the QC with genuine and minimum minors or warn"; GO:34 "zero findings (dec 101)"; ST:32 "zero QC findings (fail, minor, warn)". Confirmed, conflict C11 stands.
30. H121: PB:84 "every lever still loses at least 90% of its before share"; P12:68 same. Confirmed.
31. H126: PL4:9 recheck mode for round 2+; LJ:107 full mode after any harden touching tests/judge. Confirmed.
32. H127: DJ:709 "master reports them and Ayush decides the next step". Confirmed.

Oracle, nop, runtime
33. H142: P11:90 "the kit asks for five oracle runs. This round runs [[ORACLE_N]]"; ST:80 ORACLE COUNT. Confirmed.
34. H143: RN22:41 "Tests-channel forgery ... target 0.05 or less". Confirmed.
35. H147: RN:44 "(e) reference <= 1/4 of any stated limit with both cores busy; verifier worst case <= 90%". Confirmed.

Data and scale
36. H153: QR:59 "hidden generators must stay inside every stated bound". Confirmed (RN:8 for the schema part confirmed in item 2).

Process and caps, gate and scoring (extra, so every theme has a check)
37. H158: CR:66 order with "3 fresh blind reads"; RN:47 "no fresh blinds are required before QC on route 1". Confirmed, conflict C4 stands.
38. H163: P9:76 "Stop after 3 harden rounds in total"; ST:90 DROP RULE. Confirmed.
39. H150: LJ:105 no DONE with a running Docker job or placeholder. Confirmed.
40. H171: CR:62 and AP:28 gate tests < 85 AND rubric < 85 AND final < 40; DJ:504 and DJ:514 exceptions (warrant < 50, metered 44.05). Confirmed.
41. H175: RN:40 "(a) ... predicted final = (its new tests + predicted judge mid) / 2 <= 35"; DJ:761 (flood 38.2) and DJ:762 (hangar 41.4). Confirmed.
42. H95: LR:242 includes "same-bytes spread is about ±17.5 tests and ±20 final". Confirmed.

FIXED DURING CHECK
1. README.md and GOALS.md had been read in one cat -n call, so README numbers were first taken 41 lines too high. Corrected: the pipeline line is RM:31 (not 72), issue.py caps RM:19, U4 RM:35, U12 RM:37, U13 RM:38. CONSTRAINTS.md and CONFLICTS.md use the corrected numbers.
2. LEAK_LIBRARY.md, P13_blind_solve_v2.md and INDEX.md were also read in combined calls; their numbers were recomputed (for example LL:29 for V0-7, P13:31 and P13:32 for the blind self-check and freeze, IX:16 for P12 v5). Each recomputed line was reopened and matched.
3. state.json rule lines were first given as "rules[25] (ST:75 area)" and "rules[28]"; reopened and fixed to ST:77 and ST:80.

COULD NOT CONFIRM
1. None of the 42 checked citations failed.
2. Not checked at line level (cited from a full read but not reopened): the LR:191 to LR:199 J2b guard list (H102), P2:134 to P2:141 stage-2 table (H93), P11:76 to P11:91 lane block (H149) and the RN22:31 to RN22:34 permission block (H146). These were read in full once and the ranges match the printed numbering, but no single-line reopen was done.
3. Claims about bundle files (for example slipway instruction.md:17-19 in C26, hangar data_conventions.md:20-23) come from WHY.md and FIX_PLAN_v2.md; the bundles themselves are not in this repo and were not opened.
4. decisions.jsonl was grepped (keywords harden, lever, leak, oracle, nop, QC, judge, rubric, hidden, gate, timeout, park, plus Ayush rule words), not read in full; a rule stated there without those words could be missing.
